"""Tests de la lecture d'une seule source de sources.csv."""

import json
from pathlib import Path

import httpx
import pytest

from gazette import premiere_source
from gazette.premiere_source import (
    lire_premiere_source,
    lire_sources,
    nom_de_fichier,
    trouver_source,
)

RACINE = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"


def test_sources_csv_contient_cinq_pqr_et_cinq_pqn():
    sources = lire_sources(RACINE / "sources.csv")

    types = [source["type"] for source in sources]
    assert types.count("PQR") >= 5
    assert types.count("PQN") >= 5
    assert all(source["acces"].startswith("https://") for source in sources)


def test_trouver_source_ignore_la_casse():
    sources = [{"nom": "Le Monde", "acces": "https://exemple.fr"}]

    assert trouver_source(sources, "le monde")["acces"] == "https://exemple.fr"
    with pytest.raises(ValueError):
        trouver_source(sources, "Inconnu")


def test_nom_de_fichier_sans_accent_ni_espace():
    assert nom_de_fichier("La Dépêche du Midi") == "la-depeche-du-midi"
    assert nom_de_fichier("L'Est Républicain") == "l-est-republicain"


def test_lire_premiere_source_ecrit_un_json(tmp_path, monkeypatch):
    # On remplace le client HTTP par un faux qui renvoie la fixture : le test reste hors ligne.
    contenu = (FIXTURES / "flux_le_monde.xml").read_bytes()
    transport = httpx.MockTransport(lambda requete: httpx.Response(200, content=contenu))
    monkeypatch.setattr(premiere_source, "creer_client", lambda: httpx.Client(transport=transport))

    chemin = lire_premiere_source("Le Monde", RACINE / "sources.csv", tmp_path)

    assert chemin.name == "premiere-source-le-monde.json"
    items = json.loads(chemin.read_text(encoding="utf-8"))
    assert len(items) == 3
