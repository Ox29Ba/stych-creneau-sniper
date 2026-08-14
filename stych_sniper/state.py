"""Mémoire persistante des créneaux déjà vus.

Un simple fichier JSON contenant la liste des `slot_key` connus au dernier
passage. Sert à ne notifier QUE les nouveaux créneaux.

Sur GitHub Actions, ce fichier est re-commité par le workflow uniquement
quand il change (voir .github/workflows/check-slots.yml).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone


class State:
    def __init__(self, path: str = "state.json") -> None:
        self.path = path
        self.seen: set[str] = set()
        self.is_first_run = True
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.seen = set(data.get("seen", []))
            self.is_first_run = False
        except (json.JSONDecodeError, OSError):
            # Fichier corrompu : on repart de zéro plutôt que de planter.
            self.seen = set()
            self.is_first_run = True

    def new_keys(self, current_keys: set[str]) -> set[str]:
        """Clés présentes maintenant mais jamais vues avant."""
        return current_keys - self.seen

    def save(self, current_keys: set[str]) -> None:
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "seen": sorted(current_keys),
        }
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
