"""Tests des chemins lus depuis l'environnement."""

from pathlib import Path

from gazette.base import chemin_regles, chemin_sources, dossier_bruts, dossier_rapports


def test_chemins_par_defaut(monkeypatch):
    for variable in ("DOSSIER_BRUTS", "CHEMIN_SOURCES", "CHEMIN_REGLES", "DOSSIER_RAPPORTS"):
        monkeypatch.delenv(variable, raising=False)

    assert dossier_bruts() == Path("articles_bruts")
    assert chemin_sources() == Path("sources.csv")
    assert chemin_regles() == Path("config/regles.toml")
    assert dossier_rapports() == Path("rapports")


def test_chemins_lus_dans_l_environnement(monkeypatch):
    monkeypatch.setenv("DOSSIER_BRUTS", "/donnees/bruts")

    assert dossier_bruts() == Path("/donnees/bruts")
