"""Normalisation des textes et des dates : une fonction pure par transformation."""

import html
import re
import unicodedata
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

LONGUEUR_MAX_EXTRAIT = 300


def decoder_entites(texte: str) -> str:
    """Remplace les entités HTML (&eacute;, &#039;, &amp;...) par leurs caractères."""
    return html.unescape(texte)


def retirer_html(texte: str) -> str:
    """Retire les balises HTML ; chaque balise devient un espace pour ne pas coller les mots."""
    return re.sub(r"<[^>]+>", " ", texte)


def reparer_encodage(texte: str) -> str:
    """Répare un texte UTF-8 lu comme du Windows-1252 ("Ã©" pour "é"), sinon le rend intact."""
    # On ne tente la réparation que si on voit les marques typiques de ce défaut.
    if "Ã" not in texte and "Â" not in texte:
        return texte
    try:
        return texte.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texte


def normaliser_espaces(texte: str) -> str:
    """Remplace les espaces insécables, tabulations et retours à la ligne par un seul espace."""
    #   et   sont les espaces insécables de la typographie française (avant ":" ou "?").
    texte = texte.replace(" ", " ").replace(" ", " ")
    return " ".join(texte.split())


def normaliser_texte(texte: str | None) -> str:
    """Enchaîne les nettoyages d'un titre ou d'un extrait."""
    if not texte:
        return ""
    texte = decoder_entites(texte)
    texte = retirer_html(texte)
    # Les espaces passent avant l'encodage : une espace insécable isolée bloquerait la réparation.
    texte = normaliser_espaces(texte)
    return reparer_encodage(texte)


def borner_extrait(texte: str, longueur_max: int = LONGUEUR_MAX_EXTRAIT) -> str:
    """Coupe un extrait trop long à la fin d'un mot, pour ne garder qu'un extrait court."""
    if len(texte) <= longueur_max:
        return texte
    coupe = texte[: longueur_max - 3].rsplit(" ", 1)[0]
    return coupe + "..."


def date_en_utc(valeur: str | None) -> datetime | None:
    """Convertit une date RFC 822 (RSS) ou ISO 8601 (Atom, et certains RSS) en date UTC."""
    if not valeur:
        return None
    valeur = valeur.strip()
    try:
        date = parsedate_to_datetime(valeur)
    except (TypeError, ValueError):
        try:
            date = datetime.fromisoformat(valeur)
        except ValueError:
            return None
    # Une date sans fuseau est supposée en UTC : c'est le choix le moins surprenant.
    if date.tzinfo is None:
        date = date.replace(tzinfo=UTC)
    return date.astimezone(UTC)


def titre_pour_comparaison(titre: str) -> str:
    """Met un titre en minuscules, sans accent ni ponctuation, pour comparer deux titres."""
    sans_accents = unicodedata.normalize("NFKD", titre.lower()).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^\w ]", " ", sans_accents).split())


def similarite_jaccard(titre_a: str, titre_b: str) -> float:
    """Part des mots communs aux deux titres (indice de Jaccard), entre 0 et 1."""
    mots_a = set(titre_a.split())
    mots_b = set(titre_b.split())
    if not mots_a or not mots_b:
        return 0.0
    return len(mots_a & mots_b) / len(mots_a | mots_b)
