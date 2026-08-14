"""Journal des désistements détectés.

L'API Stych ne fournit pas d'historique des désistements passés. Ce module
construit cet historique au fil de l'eau : chaque nouveau créneau détecté
(= une place qui vient de se libérer) est ajouté à un fichier CSV avec l'heure
de détection. Au bout de quelques jours, on peut repérer les créneaux/horaires
où les désistements tombent le plus souvent.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone

FIELDS = ["detecte_le", "date", "jour", "horaire", "duree", "credits", "lieux", "moniteur"]


def append(path: str, described_slots: list[dict[str, str]]) -> None:
    """Ajoute les créneaux (déjà décrits par filters.describe) au CSV."""
    if not described_slots:
        return
    detecte_le = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fichier_existe = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if not fichier_existe:
            writer.writeheader()
        for s in described_slots:
            writer.writerow(
                {
                    "detecte_le": detecte_le,
                    "date": s.get("date", ""),
                    "jour": s.get("jour", ""),
                    "horaire": s.get("horaire", ""),
                    "duree": s.get("duree", ""),
                    "credits": s.get("credits", ""),
                    "lieux": s.get("lieu", ""),
                    "moniteur": s.get("moniteur", ""),
                }
            )
