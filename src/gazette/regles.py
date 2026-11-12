"""Règles d'exclusion : chacune a un identifiant pour que le rapport puisse compter par règle."""

import re
import tomllib
from datetime import timedelta
from pathlib import Path

from gazette.normalisation import similarite_jaccard, titre_pour_comparaison

# Ordre d'application : la première règle qui concerne un article donne la raison du rejet.
# On commence par les défauts de forme, puis la fraîcheur, le contenu, et enfin les doublons,
# qui demandent de comparer l'article aux autres.
ORDRE_DES_REGLES = [
    "R01_titre_vide",
    "R02_encodage_casse",
    "R03_sans_date",
    "R04_date_future",
    "R05_trop_ancien",
    "R06_publi",
    "R07_horoscope",
    "R08_service",
    "R09_jeux",
    "R10_doublon",
    "R11_doublon_proche",
]


def charger_regles(chemin: Path) -> dict:
    """Lit config/regles.toml."""
    with open(chemin, "rb") as fichier:
        return tomllib.load(fichier)


def titre_invalide(titre: str, regles: dict) -> bool:
    """R01 : titre vide, trop court ou gabarit non rempli."""
    if len(titre) < regles["titre"]["longueur_min"]:
        return True
    return any(re.search(gabarit, titre) for gabarit in regles["titre"]["gabarits"])


def encodage_casse(titre: str) -> bool:
    """R02 : il reste des caractères mal encodés que la normalisation n'a pas su réparer."""
    return "Ã" in titre or "�" in titre


def regle_mots_cles(article: dict, regle: dict) -> bool:
    """R06 à R09 : rubrique dans la liste, ou motif trouvé dans le lien ou dans le titre."""
    rubrique = (article["rubrique"] or "").lower()
    if rubrique and rubrique in [r.lower() for r in regle["rubriques"]]:
        return True
    if any(re.search(motif, article["lien"], re.IGNORECASE) for motif in regle.get("liens", [])):
        return True
    return any(re.search(motif, article["titre"], re.IGNORECASE) for motif in regle["motifs"])


def regle_de_doublon(titre: str, titres_gardes: list[str], regles: dict) -> str | None:
    """R10 / R11 : compare le titre aux titres gardés (déjà au format de comparaison)."""
    compare = titre_pour_comparaison(titre)
    if compare in titres_gardes:
        return "R10_doublon"
    seuil = regles["doublons"]["seuil_jaccard"]
    for autre in titres_gardes:
        if similarite_jaccard(compare, autre) >= seuil:
            return "R11_doublon_proche"
    return None


def regle_de_rejet(article: dict, titres_gardes: list[str], regles: dict) -> str | None:
    """Renvoie l'identifiant de la première règle qui rejette l'article, ou None s'il est gardé."""
    titre = article["titre"]
    if titre_invalide(titre, regles):
        return "R01_titre_vide"
    if encodage_casse(titre):
        return "R02_encodage_casse"
    if article["publie_le"] is None:
        return "R03_sans_date"

    # Les dates sont comparées à la date de récupération et non à l'heure actuelle :
    # rejouer le nettoyage plus tard donne ainsi exactement le même résultat.
    fraicheur = regles["fraicheur"]
    ecart = article["publie_le"] - article["recupere_le"]
    if ecart > timedelta(minutes=fraicheur["tolerance_futur_minutes"]):
        return "R04_date_future"
    if -ecart > timedelta(hours=fraicheur["age_max_heures"]):
        return "R05_trop_ancien"

    for regle in regles["mots_cles"]:
        if regle_mots_cles(article, regle):
            return regle["id"]

    return regle_de_doublon(titre, titres_gardes, regles)
