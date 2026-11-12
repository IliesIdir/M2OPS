"""Connexion à la base de données et chemins de stockage, lus depuis l'environnement."""

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine


def creer_moteur(url: str | None = None) -> Engine:
    """Crée le moteur SQLAlchemy à partir de DATABASE_URL (ou de l'URL donnée, pour les tests)."""
    url = url or os.environ["DATABASE_URL"]
    # pool_pre_ping vérifie la connexion avant usage : utile après un redémarrage de PostgreSQL.
    return create_engine(url, pool_pre_ping=True)


def dossier_bruts() -> Path:
    """Renvoie le dossier du stockage brut (articles_bruts/ par défaut)."""
    return Path(os.environ.get("DOSSIER_BRUTS", "articles_bruts"))


def chemin_sources() -> Path:
    """Renvoie le chemin de sources.csv."""
    return Path(os.environ.get("CHEMIN_SOURCES", "sources.csv"))
