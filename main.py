#!/usr/bin/env python3
"""Point d'entrée du bot : une exécution = une vérification.

Usage :
    python main.py                 # vérifie et notifie les nouveaux créneaux
    python main.py --list-lieux    # liste tous les lieux (id, dep, ville, arrêt)
    python main.py --dry-run       # affiche les créneaux trouvés sans notifier
    python main.py --test-telegram # envoie un message de test puis quitte

La planification (« toutes les 5 min ») est gérée à l'extérieur :
GitHub Actions (voir .github/workflows/check-slots.yml) ou cron local.
"""

from __future__ import annotations

import argparse
import sys

from stych_sniper.client import StychClient, StychError
from stych_sniper.config import load_config, load_secrets
from stych_sniper.filters import describe, matches, slot_key
from stych_sniper.notifier import TelegramNotifier, format_slots
from stych_sniper.state import State


def log(msg: str) -> None:
    print(msg, flush=True)


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
    parser.add_argument("--list-lieux", action="store_true", help="Lister les lieux puis quitter")
    parser.add_argument("--dry-run", action="store_true", help="Ne pas envoyer de notification")
    parser.add_argument("--test-telegram", action="store_true", help="Envoyer un message de test puis quitter")
    args = parser.parse_args()

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
    else:
        log("Aucun nouveau créneau.")

    state.save(keys_now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
