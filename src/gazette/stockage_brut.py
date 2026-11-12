"""Stockage brut : un fichier JSON par item, tel que reçu, sans doublon pour (source, lien)."""

import hashlib
import json
from pathlib import Path

from gazette.premiere_source import nom_de_fichier


def identifiant_item(source: str, lien: str) -> str:
    """Calcule l'identifiant d'un item à partir de sa clé naturelle (source, lien)."""
    # On ne se fie pas au guid, qui n'est pas fiable partout : le lien l'est davantage.
    # 16 caractères hexadécimaux (64 bits) suffisent pour quelques milliers d'items par jour.
    return hashlib.sha256(f"{source}|{lien}".encode()).hexdigest()[:16]


def chemin_item(dossier: Path, source: str, identifiant: str) -> Path:
    """Renvoie le chemin du fichier d'un item : un sous-dossier par source."""
    return dossier / nom_de_fichier(source) / f"{identifiant}.json"


def ecrire_item(dossier: Path, item: dict, recupere_le: str) -> bool:
    """Écrit l'item s'il n'existe pas encore ; renvoie True s'il a été écrit, sinon False."""
    identifiant = identifiant_item(item["source"], item["lien"])
    chemin = chemin_item(dossier, item["source"], identifiant)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    contenu = {
        "id": identifiant,
        "source": item["source"],
        "lien": item["lien"],
        "titre": item["titre"],
        "resume": item["resume"],
        "publie_le": item["publie_le"],
        "recupere_le": recupere_le,
        "rubrique": item["rubrique"],
        "payload": item["payload"],
    }
    # Le mode "x" crée le fichier seulement s'il n'existe pas : deux passages ne peuvent pas
    # écrire deux fois le même item, ce qui rend la collecte idempotente.
    try:
        with open(chemin, "x", encoding="utf-8") as fichier:
            json.dump(contenu, fichier, ensure_ascii=False, indent=2)
    except FileExistsError:
        return False
    return True
