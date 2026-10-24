#!/usr/bin/env python3
"""Point d'entrée du bot : une exécution = une vérification.

Usage :
    python main.py                 # vérifie et notifie les nouveaux créneaux
    python main.py --list-lieux    # liste tous les lieux (id, dep, ville, arrêt)
    python main.py --dry-run       # affiche les créneaux trouvés sans notifier
    python main.py --test-telegram # envoie un message de test puis quitte
    python main.py --loop 30 --until 2026-11-02  # veille locale en continu

La planification (« toutes les 5 min ») est gérée à l'extérieur :
GitHub Actions (voir .github/workflows/check-slots.yml) ou cron local.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import date

from stych_sniper import history
from stych_sniper.client import StychClient, StychError
from stych_sniper.config import load_config, load_secrets
from stych_sniper.filters import describe, matches, slot_key
from stych_sniper.notifier import TelegramNotifier, format_slots
from stych_sniper.state import State


def log(msg: str) -> None:
    print(msg, flush=True)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def sync_depot() -> None:
    """Sur GitHub Actions, rattrape les commits poussés depuis le déclenchement.

    Un run planifié démarre sur le commit de son déclenchement, pas sur le
    dernier : s'il a attendu derrière un run qui a poussé l'état, son push
    final serait refusé. On avance donc la copie (au début et à la fin) en
    gardant l'état local, plus récent, et en fusionnant l'historique.
    """
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    fetch = _git("fetch", "--quiet", "origin", "main")
    if fetch.returncode:
        log(f"Synchro du dépôt impossible : {fetch.stderr.strip()}")
        return
    modifies = {
        f: open(f, encoding="utf-8").read()
        for f in ("state.json", "historique.csv")
        if os.path.exists(f) and _git("diff", "--quiet", "HEAD", "--", f).returncode
    }
    reset = _git("reset", "--hard", "--quiet", "FETCH_HEAD")
    if reset.returncode:
        log(f"Synchro du dépôt impossible : {reset.stderr.strip()}")
    for f, contenu in modifies.items():
        if f == "historique.csv" and os.path.exists(f):
            lignes = open(f, encoding="utf-8").read().splitlines()
            lignes += [l for l in contenu.splitlines() if l not in set(lignes)]
            contenu = "\n".join(lignes) + "\n"
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(contenu)


def cmd_list_lieux(client: StychClient) -> int:
    _, lieux_par_id = client.fetch_propositions()
    par_dep: dict[str, list[dict]] = {}
    for lieu in lieux_par_id.values():
        par_dep.setdefault(str(lieu.get("dep_code")), []).append(lieu)

    log(f"{len(lieux_par_id)} lieux disponibles :\n")
    for dep in sorted(par_dep):
        libelle = par_dep[dep][0].get("dep_libelle", "")
        log(f"── Département {dep} ({libelle}) ──")
        for lieu in sorted(par_dep[dep], key=lambda x: str(x.get("ville"))):
            log(
                f"  id={lieu['id_liste_adresse_cours']:>4}  "
                f"{lieu.get('code_postal')} {lieu.get('ville'):<22} "
                f"{lieu.get('intitule', '').strip()}"
            )
        log("")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Veille des créneaux de conduite Stych.")
    parser.add_argument("--config", default="config.yaml", help="Fichier de filtres (défaut: config.yaml)")
    parser.add_argument("--state", default="state.json", help="Fichier d'état (défaut: state.json)")
    parser.add_argument("--history", default="historique.csv", help="Journal des désistements (défaut: historique.csv)")
    parser.add_argument("--list-lieux", action="store_true", help="Lister les lieux puis quitter")
    parser.add_argument("--dry-run", action="store_true", help="Ne pas envoyer de notification")
    parser.add_argument("--test-telegram", action="store_true", help="Envoyer un message de test puis quitter")
    parser.add_argument("--loop", type=int, default=0, help="Vérifier en continu toutes les N secondes")
    parser.add_argument("--until", help="En mode --loop : s'arrêter après cette date (AAAA-MM-JJ)")
    args = parser.parse_args()

    sync_depot()
    secrets = load_secrets()

    # --- Test Telegram isolé (ne touche pas à Stych) ---
    if args.test_telegram:
        TelegramNotifier(secrets.telegram_token, secrets.telegram_chat_id).send(
            "✅ Test réussi : ton bot Stych est bien connecté à Telegram."
        )
        log("Message de test envoyé.")
        return 0

    config = load_config(args.config)

    # --- Connexion Stych ---
    client = StychClient(secrets.stych_email, secrets.stych_password)
    try:
        log("Connexion à Stych…")
        client.login()
    except StychError as exc:
        log(f"ERREUR : {exc}")
        return 1

    if args.list_lieux:
        return cmd_list_lieux(client)

    # Mode boucle : en ligne de commande, ou via `options.boucle` du config.yaml
    # (c'est ainsi que GitHub Actions veille en continu sans toucher au workflow).
    boucle = config.options.get("boucle") or {}
    intervalle = args.loop or boucle.get("intervalle_s") or 0
    fin = args.until or boucle.get("jusqu_au")
    until = date.fromisoformat(str(fin)) if fin else None
    if not intervalle or (until and date.today() > until):
        code = check(client, config, secrets, args)
        sync_depot()
        return code

    # --- Mode boucle : on garde la session, on se reconnecte si elle expire ---
    stop_at = time.monotonic() + float(boucle.get("duree_max_s") or "inf")
    log(f"Veille en continu toutes les {intervalle} s" + (f" jusqu'au {until}." if until else "."))
    while (until is None or date.today() <= until) and time.monotonic() < stop_at:
        try:
            check(client, config, secrets, args)
        except StychError as exc:
            log(f"Session perdue ({exc}), reconnexion…")
            try:
                client.login()
            except StychError as exc2:
                log(f"ERREUR : {exc2}")
        except Exception as exc:  # réseau, Telegram… : on ne s'arrête pas pour ça
            log(f"ERREUR inattendue : {exc}")
        time.sleep(intervalle)
    log("Fin de la veille (date ou durée max atteinte).")
    sync_depot()
    return 0


def check(client: StychClient, config, secrets, args) -> int:
    # --- Récupération + filtrage ---
    propositions, lieux_par_id = client.fetch_propositions()
    log(f"{len(propositions)} créneaux au total sur le planning.")

    retenus = [p for p in propositions if matches(p, lieux_par_id, config.filtres)]
    log(f"{len(retenus)} créneaux correspondent à tes filtres.")

    keys_now = {slot_key(p) for p in retenus}
    state = State(args.state)

    # --- Détection des nouveaux ---
    if config.options.get("seulement_nouveaux", True):
        nouveaux_keys = state.new_keys(keys_now)
    else:
        nouveaux_keys = keys_now

    nouveaux = [p for p in retenus if slot_key(p) in nouveaux_keys]
    nouveaux.sort(key=lambda p: (str(p.get("info_date")), str(p.get("heure_debut"))))

    notifier = TelegramNotifier(secrets.telegram_token, secrets.telegram_chat_id)

    # --- Premier lancement : éviter le spam ---
    premier = state.is_first_run and config.options.get("seulement_nouveaux", True)
    if premier and config.options.get("resume_au_premier_lancement", True):
        log("Premier lancement : mémorisation de l'état, envoi d'un simple résumé.")
        if not args.dry_run:
            notifier.send(
                f"🚗 Bot Stych démarré.\n"
                f"{len(retenus)} créneau(x) correspondent déjà à tes filtres. "
                f"Je te préviens dès qu'un NOUVEAU se libère."
            )
        state.save(keys_now)
        return 0

    # --- Notification des nouveaux créneaux ---
    if nouveaux:
        log(f"🔔 {len(nouveaux)} nouveau(x) créneau(x) !")
        descriptions = [describe(p, lieux_par_id) for p in nouveaux]
        message = format_slots(
            descriptions,
            titre=f"🚗 {len(nouveaux)} nouveau(x) créneau(x) de conduite !",
        )
        if args.dry_run:
            log(message)
        else:
            notifier.send(message)
            # On journalise les désistements détectés pour bâtir un historique.
            history.append(args.history, descriptions)
    else:
        log("Aucun nouveau créneau.")

    state.save(keys_now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
