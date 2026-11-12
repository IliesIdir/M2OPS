"""Téléchargement d'un flux RSS ou Atom et extraction de ses items."""

import feedparser
import httpx

# On se présente honnêtement aux éditeurs : nom du projet et adresse du dépôt.
USER_AGENT = "gazette-m2ops/0.1 (projet etudiant EFREI M2; +https://github.com/IliesIdir/M2OPS)"
TIMEOUT_SECONDES = 20

# On retire du payload ce que le bornage interdit de stocker : les noms de personnes
# (auteurs, crédits photo), le texte intégral (content), les images et leurs liens.
# Les champs "*_parsed" sont des dates déjà converties par feedparser, non sérialisables en JSON.
PREFIXES_EXCLUS = ("author", "content", "credit", "media_", "contributor", "publisher", "image")
CHAMPS_EXCLUS = {"links", "href", "comments"}


def creer_client() -> httpx.Client:
    """Crée le client HTTP utilisé pour toutes les requêtes vers les éditeurs."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDES,
        follow_redirects=True,
    )


def telecharger_flux(client: httpx.Client, url: str) -> bytes:
    """Télécharge un flux et renvoie son contenu ; lève une erreur si le code HTTP n'est pas 2xx."""
    reponse = client.get(url)
    reponse.raise_for_status()
    return reponse.content


def nettoyer_payload(entree: dict) -> dict:
    """Renvoie l'entrée du flux sans les champs que le bornage interdit de stocker."""
    payload = {}
    for cle, valeur in entree.items():
        if cle.startswith(PREFIXES_EXCLUS) or cle in CHAMPS_EXCLUS or cle.endswith("_parsed"):
            continue
        payload[cle] = valeur
    return payload


def premiere_rubrique(entree: dict) -> str | None:
    """Renvoie la première catégorie de l'item, qu'on utilise comme rubrique."""
    tags = entree.get("tags") or []
    if tags and tags[0].get("term"):
        return tags[0]["term"]
    return None


def parser_flux(contenu: bytes, source: str) -> list[dict]:
    """Lit un flux RSS ou Atom et renvoie ses items avec les champs utiles à la gazette."""
    # On utilise feedparser plutôt qu'un parseur maison car il gère déjà RSS, Atom,
    # les encodages et les nombreux formats de date.
    flux = feedparser.parse(contenu)
    items = []
    for entree in flux.entries:
        lien = entree.get("link")
        # Sans lien, on ne peut ni dédoublonner ni renvoyer le lecteur vers l'article.
        if not lien:
            continue
        items.append(
            {
                "source": source,
                "lien": lien,
                "titre": entree.get("title", ""),
                "resume": entree.get("summary", ""),
                # On garde la date telle que reçue ; sa conversion en UTC se fait au nettoyage.
                "publie_le": entree.get("published") or entree.get("updated"),
                "rubrique": premiere_rubrique(entree),
                "payload": nettoyer_payload(entree),
            }
        )
    return items
