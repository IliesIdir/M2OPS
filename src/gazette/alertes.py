"""Envoi des alertes vers le canal Discord de l'équipe."""

import logging
import os

import httpx

journal = logging.getLogger(__name__)


def envoyer_alerte(message: str) -> bool:
    """Envoie un message au webhook Discord ; renvoie False si l'envoi n'a pas pu se faire."""
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    # Sans webhook configuré, on n'interrompt pas le pipeline : l'alerte reste dans les journaux.
    if not url:
        journal.warning("alerte non envoyee (DISCORD_WEBHOOK_URL absent) : %s", message)
        return False
    try:
        reponse = httpx.post(url, json={"content": f"[gazette] {message}"}, timeout=10)
        reponse.raise_for_status()
    except httpx.HTTPError as erreur:
        journal.error("alerte non envoyee (%s) : %s", erreur, message)
        return False
    journal.info("alerte envoyee : %s", message)
    return True
