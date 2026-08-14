"""Chargement de la configuration.

Deux sources, volontairement séparées :
  - les **filtres** viennent d'un fichier YAML (public, versionnable) ;
  - les **secrets** viennent des variables d'environnement / `.env`
    (jamais versionnés).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml
from dotenv import load_dotenv

# Valeurs par défaut : tout est « pas de filtre ». Sert de garde-fou si
# une clé manque dans le config.yaml de l'utilisateur.
_DEFAULT_FILTRES: dict[str, Any] = {
    "departements": [],
    "villes": [],
    "codes_postaux": [],
    "arrets": [],
    "lieux_ids": [],
    "duree_min": None,
    "duree_max": None,
    "durees_exactes": [],
    "credits_max": None,
    "jours": [],
    "date_debut": None,
    "date_fin": None,
    "heure_min": None,
    "heure_max": None,
    "moniteurs": [],
}

_DEFAULT_OPTIONS: dict[str, Any] = {
    "seulement_nouveaux": True,
    "resume_au_premier_lancement": True,
}


@dataclass
class Secrets:
    stych_email: str
    stych_password: str
    telegram_token: str
    telegram_chat_id: str


@dataclass
class Config:
    filtres: dict[str, Any] = field(default_factory=lambda: dict(_DEFAULT_FILTRES))
    options: dict[str, Any] = field(default_factory=lambda: dict(_DEFAULT_OPTIONS))


def load_config(path: str = "config.yaml") -> Config:
    """Charge les filtres depuis le YAML (fusionnés avec les défauts)."""
    data: dict[str, Any] = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}

    filtres = {**_DEFAULT_FILTRES, **(data.get("filtres") or {})}
    options = {**_DEFAULT_OPTIONS, **(data.get("options") or {})}
    return Config(filtres=filtres, options=options)


def load_secrets() -> Secrets:
    """Charge les secrets depuis l'environnement (et `.env` en local)."""
    load_dotenv()  # ne fait rien si le fichier .env est absent (ex: CI)

    def _req(name: str) -> str:
        val = os.environ.get(name, "").strip()
        if not val:
            raise SystemExit(
                f"Variable manquante : {name}. "
                f"Renseigne-la dans .env (local) ou dans les Secrets GitHub (CI)."
            )
        return val

    return Secrets(
        stych_email=_req("STYCH_EMAIL"),
        stych_password=_req("STYCH_PASSWORD"),
        telegram_token=_req("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_req("TELEGRAM_CHAT_ID"),
    )
