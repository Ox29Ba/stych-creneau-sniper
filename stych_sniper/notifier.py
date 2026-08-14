"""Envoi des notifications via l'API Bot Telegram."""

from __future__ import annotations

import html
import requests

_API = "https://api.telegram.org/bot{token}/sendMessage"
_TELEGRAM_LIMIT = 4096  # taille max d'un message


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, timeout: int = 20) -> None:
        self.token = token
        self.chat_id = chat_id
        self.timeout = timeout

    def send(self, text: str) -> None:
        """Envoie un message (HTML), découpé si trop long."""
        for chunk in _split(text, _TELEGRAM_LIMIT):
            resp = requests.post(
                _API.format(token=self.token),
                json={
                    "chat_id": self.chat_id,
                    "text": chunk,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Telegram a répondu {resp.status_code} : {resp.text[:300]}"
                )


def format_slots(slots: list[dict[str, str]], titre: str) -> str:
    """Met en forme une liste de créneaux (déjà décrits par filters.describe)."""
    lignes = [f"<b>{html.escape(titre)}</b>", ""]
    for s in slots:
        jour = f"{s['jour'].capitalize()} " if s.get("jour") else ""
        credits = f" · {s['credits']} crédit(s)" if s.get("credits") else ""
        moniteur = f"\n   👤 {html.escape(s['moniteur'])}" if s.get("moniteur") else ""
        lignes.append(
            f"📅 <b>{jour}{html.escape(s['date'])}</b> · 🕒 {html.escape(s['horaire'])} "
            f"({html.escape(s['duree'])}{credits})\n"
            f"   📍 {html.escape(s['lieu'])}{moniteur}"
        )
        lignes.append("")
    return "\n".join(lignes).strip()


def _split(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit:
            if current:
                chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks
