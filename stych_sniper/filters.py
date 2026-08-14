"""Application des filtres utilisateur sur les créneaux.

Un créneau (`proposition`) ressemble à :
    {
      "info_date": "2026-08-21", "id_jour": "5",
      "heure_debut": "07:00:00", "heure_fin": "08:30:00",
      "heure_debut_fr": "7h00", "heure_fin_fr": "8h30",
      "nb_heure": 1.5, "nb_credit": 2,
      "id_lac": "210", "ids_lac_possible": ["210", "238"],
      "moniteur": "GREGORY H.", ...
    }

Les lieux sont indexés par `id_lac` dans `lieux_par_id` (voir client.py).
"""

from __future__ import annotations

from typing import Any

_JOURS_FR = {1: "lundi", 2: "mardi", 3: "mercredi", 4: "jeudi", 5: "vendredi", 6: "samedi", 7: "dimanche"}


# --------------------------------------------------------------------------- #
# Résolution des lieux
# --------------------------------------------------------------------------- #
def _candidate_ids(prop: dict[str, Any]) -> list[str]:
    """Lieux où ce créneau est réellement réservable.

    On s'aligne EXACTEMENT sur la logique du site (reservationPlanning.js) qui
    filtre les lieux sur `ids_lac_possible` uniquement. `ids_lac_possible_origine`
    est un ensemble plus large (zone d'origine du moniteur) que le site n'utilise
    PAS pour la réservation : l'inclure ferait matcher des créneaux non
    réservables au lieu demandé.
    """
    ids: list[str] = []
    for key in ("id_lac", "ids_lac_possible"):
        val = prop.get(key)
        if isinstance(val, list):
            ids.extend(str(x) for x in val)
        elif val:
            ids.append(str(val))
    # unique en gardant l'ordre
    seen: set[str] = set()
    return [i for i in ids if not (i in seen or seen.add(i))]


def resolve_locations(prop: dict[str, Any], lieux_par_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Renvoie les fiches lieu correspondant au créneau."""
    return [lieux_par_id[i] for i in _candidate_ids(prop) if i in lieux_par_id]


def primary_location(prop: dict[str, Any], lieux_par_id: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Lieu principal (celui affiché par défaut sur le site)."""
    lieu = lieux_par_id.get(str(prop.get("id_lac")))
    if lieu:
        return lieu
    locs = resolve_locations(prop, lieux_par_id)
    return locs[0] if locs else None


# --------------------------------------------------------------------------- #
# Identité stable d'un créneau (pour la détection des nouveaux)
# --------------------------------------------------------------------------- #
def slot_key(prop: dict[str, Any]) -> str:
    return "|".join(
        str(prop.get(k, ""))
        for k in ("info_date", "heure_debut", "heure_fin", "id_lac", "moniteur")
    )


# --------------------------------------------------------------------------- #
# Helpers de comparaison
# --------------------------------------------------------------------------- #
def _to_minutes(hhmm: str) -> int | None:
    """'17:00' ou '07:45:00' -> minutes depuis minuit."""
    if not hhmm:
        return None
    parts = str(hhmm).split(":")
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return None


def _as_float(val: Any) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Filtre principal
# --------------------------------------------------------------------------- #
def matches(prop: dict[str, Any], lieux_par_id: dict[str, dict[str, Any]], f: dict[str, Any]) -> bool:
    """True si le créneau passe TOUS les critères définis dans `f`."""

    # --- Lieu : au moins un lieu candidat doit satisfaire au moins un critère lieu ---
    lieu_criteres = any(
        f.get(k) for k in ("departements", "villes", "codes_postaux", "arrets", "lieux_ids")
    )
    if lieu_criteres:
        locs = resolve_locations(prop, lieux_par_id)
        if not any(_lieu_match(loc, prop, f) for loc in locs) and not _lieu_match_by_id(prop, f):
            return False

    # --- Durée ---
    duree = _as_float(prop.get("nb_heure"))
    if f.get("durees_exactes"):
        cibles = {_as_float(x) for x in f["durees_exactes"]}
        if duree not in cibles:
            return False
    if f.get("duree_min") is not None and (duree is None or duree < float(f["duree_min"])):
        return False
    if f.get("duree_max") is not None and (duree is None or duree > float(f["duree_max"])):
        return False

    # --- Crédits ---
    if f.get("credits_max") is not None:
        credit = _as_float(prop.get("nb_credit"))
        if credit is None or credit > float(f["credits_max"]):
            return False

    # --- Jour de la semaine ---
    if f.get("jours"):
        try:
            jour = int(prop.get("id_jour"))
        except (TypeError, ValueError):
            return False
        if jour not in {int(j) for j in f["jours"]}:
            return False

    # --- Plage de dates (ISO -> comparaison lexicographique OK) ---
    date = str(prop.get("info_date", ""))
    if f.get("date_debut") and date < str(f["date_debut"]):
        return False
    if f.get("date_fin") and date > str(f["date_fin"]):
        return False

    # --- Plage horaire (sur l'heure de début) ---
    debut = _to_minutes(prop.get("heure_debut"))
    if f.get("heure_min") is not None:
        borne = _to_minutes(f["heure_min"])
        if debut is None or (borne is not None and debut < borne):
            return False
    if f.get("heure_max") is not None:
        borne = _to_minutes(f["heure_max"])
        if debut is None or (borne is not None and debut > borne):
            return False

    # --- Moniteur (sous-chaîne, insensible à la casse) ---
    if f.get("moniteurs"):
        moniteur = str(prop.get("moniteur", "")).lower()
        if not any(str(m).lower() in moniteur for m in f["moniteurs"]):
            return False

    return True


def _lieu_match(loc: dict[str, Any], prop: dict[str, Any], f: dict[str, Any]) -> bool:
    if f.get("departements") and str(loc.get("dep_code")) in {str(d) for d in f["departements"]}:
        return True
    if f.get("villes") and any(
        str(v).lower() in str(loc.get("ville", "")).lower() for v in f["villes"]
    ):
        return True
    if f.get("codes_postaux") and str(loc.get("code_postal")) in {str(c) for c in f["codes_postaux"]}:
        return True
    if f.get("arrets") and any(
        str(a).lower() in str(loc.get("intitule", "")).lower() for a in f["arrets"]
    ):
        return True
    return False


def _lieu_match_by_id(prop: dict[str, Any], f: dict[str, Any]) -> bool:
    if not f.get("lieux_ids"):
        return False
    wanted = {str(x) for x in f["lieux_ids"]}
    return any(i in wanted for i in _candidate_ids(prop))


# --------------------------------------------------------------------------- #
# Description lisible (pour Telegram / logs)
# --------------------------------------------------------------------------- #
def describe(prop: dict[str, Any], lieux_par_id: dict[str, dict[str, Any]]) -> dict[str, str]:
    # Un créneau peut être réservable sur plusieurs points de rendez-vous :
    # on les liste tous (lieu principal en premier) pour ne pas induire en erreur.
    prim_id = str(prop.get("id_lac"))
    locs = sorted(
        resolve_locations(prop, lieux_par_id),
        key=lambda l: 0 if str(l.get("id_liste_adresse_cours")) == prim_id else 1,
    )
    noms, vus = [], set()
    for loc in locs:
        lid = str(loc.get("id_liste_adresse_cours"))
        if lid in vus:
            continue
        vus.add(lid)
        noms.append(f"{loc.get('intitule', '').strip()} ({loc.get('ville')})")
    lieu_txt = " · ".join(noms) if noms else f"lieu #{prop.get('id_lac')}"

    duree = _as_float(prop.get("nb_heure")) or 0
    heures = int(duree)
    minutes = int(round((duree - heures) * 60))
    duree_txt = (f"{heures}h" if heures else "") + (f"{minutes:02d}" if minutes else ("00" if heures else ""))
    duree_txt = duree_txt or f"{duree}h"

    try:
        jour_txt = _JOURS_FR.get(int(prop.get("id_jour")), "")
    except (TypeError, ValueError):
        jour_txt = ""

    return {
        "date": str(prop.get("info_date", "")),
        "jour": jour_txt,
        "horaire": f"{prop.get('heure_debut_fr', '')}–{prop.get('heure_fin_fr', '')}",
        "lieu": lieu_txt,
        "duree": duree_txt,
        "credits": str(prop.get("nb_credit", "")),
        "moniteur": str(prop.get("moniteur", "")).strip(),
    }
