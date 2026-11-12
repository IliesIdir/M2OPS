"""Tests de la table sources : synchronisation depuis le CSV et suivi des échecs."""

from datetime import UTC, datetime
from pathlib import Path

from gazette.sources import (
    enregistrer_echec,
    enregistrer_reussite,
    lire_source,
    lister_sources_actives,
    reactiver_source,
    synchroniser_sources,
)

RACINE = Path(__file__).parent.parent
ENTETE = "nom,type,region,acces,conditions,notes\n"


def ecrire_csv(chemin, lignes):
    chemin.write_text(ENTETE + "".join(lignes), encoding="utf-8")


def test_synchroniser_copie_le_vrai_sources_csv(moteur):
    resultat = synchroniser_sources(moteur, RACINE / "sources.csv")

    assert resultat["synchronisees"] == 10
    assert len(lister_sources_actives(moteur)) == 10


def test_synchroniser_deux_fois_ne_cree_pas_de_doublon(moteur, tmp_path):
    csv = tmp_path / "sources.csv"
    ecrire_csv(csv, ["A,PQR,r,https://a.fr/rss,c,n\n", "B,PQN,national,https://b.fr/rss,c,n\n"])

    synchroniser_sources(moteur, csv)
    synchroniser_sources(moteur, csv)

    assert [source["nom"] for source in lister_sources_actives(moteur)] == ["A", "B"]


def test_synchroniser_garde_l_etat_et_oublie_l_etag_si_l_adresse_change(moteur, tmp_path):
    csv = tmp_path / "sources.csv"
    ecrire_csv(csv, ["A,PQR,r,https://a.fr/rss,c,n\n"])
    synchroniser_sources(moteur, csv)
    enregistrer_reussite(moteur, "A", datetime.now(UTC), '"v1"', None)
    enregistrer_echec(moteur, "A")

    ecrire_csv(csv, ["A,PQR,r,https://a.fr/nouveau-rss,c,n\n"])
    synchroniser_sources(moteur, csv)

    source = lire_source(moteur, "A")
    assert source["url_flux"] == "https://a.fr/nouveau-rss"
    assert source["etag"] is None
    assert source["echecs_consecutifs"] == 1


def test_une_source_retiree_du_csv_est_desactivee(moteur, tmp_path):
    csv = tmp_path / "sources.csv"
    ecrire_csv(csv, ["A,PQR,r,https://a.fr/rss,c,n\n", "B,PQN,national,https://b.fr/rss,c,n\n"])
    synchroniser_sources(moteur, csv)

    ecrire_csv(csv, ["A,PQR,r,https://a.fr/rss,c,n\n"])
    resultat = synchroniser_sources(moteur, csv)

    assert resultat["desactivees"] == 1
    assert [source["nom"] for source in lister_sources_actives(moteur)] == ["A"]


def test_trois_echecs_mettent_en_sommeil_et_la_reussite_remet_a_zero(moteur, tmp_path):
    csv = tmp_path / "sources.csv"
    ecrire_csv(csv, ["A,PQR,r,https://a.fr/rss,c,n\n"])
    synchroniser_sources(moteur, csv)

    assert enregistrer_echec(moteur, "A") is False
    enregistrer_reussite(moteur, "A", datetime.now(UTC), None, None)
    assert lire_source(moteur, "A")["echecs_consecutifs"] == 0

    assert [enregistrer_echec(moteur, "A") for _ in range(3)] == [False, False, True]
    assert not lire_source(moteur, "A")["actif"]

    reactiver_source(moteur, "A")
    source = lire_source(moteur, "A")
    assert source["actif"]
    assert source["echecs_consecutifs"] == 0
