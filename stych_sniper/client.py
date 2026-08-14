"""Client HTTP pour Stych : connexion + récupération des créneaux.

Fonctionnement (rétro-ingénierie des requêtes du site) :
  1. POST sur /connexion/0/record3 avec `email` + `mdp`  -> pose le cookie
     de session (HttpOnly) dans la requests.Session.
  2. POST sur /elearning/planning-conduite/get-planning-proposition avec un
     corps vide -> renvoie tout le planning au format JSON.

Aucun CAPTCHA, aucun jeton CSRF : une simple session `requests` suffit.
"""

from __future__ import annotations

from typing import Any

import requests

BASE_URL = "https://www.stych.fr"
LOGIN_URL = f"{BASE_URL}/connexion/0/record3"
PLANNING_URL = f"{BASE_URL}/elearning/planning-conduite/get-planning-proposition"

# User-Agent d'un vrai navigateur : certains serveurs rejettent les UA vides.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class StychError(RuntimeError):
    """Erreur métier (connexion échouée, réponse inattendue, etc.)."""


class StychClient:
    def __init__(self, email: str, password: str, timeout: int = 30) -> None:
        self.email = email
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": _USER_AGENT,
                "Accept-Language": "fr-FR,fr;q=0.9",
            }
        )

    # ------------------------------------------------------------------ #
    def login(self) -> None:
        """Se connecte à Stych. Lève StychError si les identifiants sont faux."""
        # 1) On visite la page de connexion pour récupérer d'éventuels cookies initiaux.
        try:
            self.session.get(f"{BASE_URL}/connexion", timeout=self.timeout)
        except requests.RequestException as exc:
            raise StychError(f"Impossible d'atteindre Stych : {exc}") from exc

        # 2) On envoie le formulaire de connexion.
        payload = {
            "email": self.email,
            "mdp": self.password,
            "mdp_forgotten": "",
            "remember_me": "on",
            "submit": "Connexion",
        }
        try:
            self.session.post(
                LOGIN_URL,
                data=payload,
                timeout=self.timeout,
                headers={"Referer": f"{BASE_URL}/connexion"},
            )
        except requests.RequestException as exc:
            raise StychError(f"Échec de la requête de connexion : {exc}") from exc

        # 3) L'endpoint de login renvoie un corps vide : le vrai test de succès,
        #    c'est de réussir à lire le planning (qui exige une session valide).
        if not self._is_authenticated():
            raise StychError(
                "Connexion refusée. Vérifie STYCH_EMAIL / STYCH_PASSWORD "
                "(et que le compte n'a pas de double authentification)."
            )

    def _is_authenticated(self) -> bool:
        try:
            self._fetch_planning_raw()
            return True
        except StychError:
            return False

    # ------------------------------------------------------------------ #
    def _fetch_planning_raw(self) -> dict[str, Any]:
        """Appelle l'API planning et renvoie le JSON, ou lève StychError."""
        try:
            resp = self.session.post(
                PLANNING_URL,
                data="",
                timeout=self.timeout,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"{BASE_URL}/elearning/formation/conduite/reservation/planning",
                },
            )
        except requests.RequestException as exc:
            raise StychError(f"Erreur réseau sur l'API planning : {exc}") from exc

        # Si la session n'est pas valide, Stych renvoie du HTML (redirection login)
        # au lieu du JSON attendu -> json() échoue, on considère non authentifié.
        try:
            data = resp.json()
        except ValueError as exc:
            raise StychError("Réponse non-JSON (session expirée ?).") from exc

        if not isinstance(data, dict) or "rowsProposition" not in data:
            raise StychError("Réponse JSON inattendue (clé 'rowsProposition' absente).")
        return data

    # ------------------------------------------------------------------ #
    def fetch_propositions(self) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        """Renvoie (liste des créneaux, index des lieux par id_lac)."""
        data = self._fetch_planning_raw()
        propositions = data.get("rowsProposition") or []
        lieux_par_id = {
            str(lieu["id_liste_adresse_cours"]): lieu
            for lieu in (data.get("rowsPointDeCours") or [])
        }
        return propositions, lieux_par_id
