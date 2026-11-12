"""Lecture de bout en bout d'une seule source de sources.csv, écrite dans un fichier JSON."""

import csv
import json
import logging
import unicodedata
from pathlib import Path

from gazette.flux import creer_client, parser_flux, telecharger_flux

journal = logging.getLogger(__name__)


def lire_sources(chemin: Path) -> list[dict]:
    """Lit sources.csv et renvoie une liste de dictionnaires, une ligne par source."""
    with open(chemin, encoding="utf-8", newline="") as fichier:
        return list(csv.DictReader(fichier))


def trouver_source(sources: list[dict], nom: str) -> dict:
    """Renvoie la source dont le nom correspond, sans tenir compte de la casse."""
    for source in sources:
        if source["nom"].lower() == nom.lower():
            return source
    raise ValueError(f"Source inconnue dans sources.csv : {nom}")


def nom_de_fichier(texte: str) -> str:
    """Transforme un nom de source en nom de fichier sans accent ni espace."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
    mots = "".join(c if c.isalnum() else " " for c in sans_accents.lower()).split()
    return "-".join(mots)


def lire_premiere_source(nom: str, chemin_sources: Path, dossier_sortie: Path) -> Path:
    """Télécharge le flux d'une source, le parse et écrit ses items dans un fichier JSON."""
    source = trouver_source(lire_sources(chemin_sources), nom)
    with creer_client() as client:
        contenu = telecharger_flux(client, source["acces"])
    items = parser_flux(contenu, source["nom"])

    dossier_sortie.mkdir(parents=True, exist_ok=True)
    chemin = dossier_sortie / f"premiere-source-{nom_de_fichier(source['nom'])}.json"
    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump(items, fichier, ensure_ascii=False, indent=2)
    journal.info("source=%s items=%d fichier=%s", source["nom"], len(items), chemin)
    return chemin
