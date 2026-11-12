"""Tests du collecteur contre un faux éditeur HTTP local : panne, doublons, en-têtes."""

from pathlib import Path

from gazette import collecte
from gazette.collecte import collecter_tout
from gazette.flux import USER_AGENT
from gazette.sources import lire_source, synchroniser_sources

FLUX_LE_MONDE = (Path(__file__).parent / "fixtures" / "flux_le_monde.xml").read_bytes()


def declarer_source(moteur, tmp_path, url):
    csv = tmp_path / "sources.csv"
    csv.write_text(
        f"nom,type,region,acces,conditions,notes\nLe Monde,PQN,national,{url},c,n\n",
        encoding="utf-8",
    )
    synchroniser_sources(moteur, csv)


def compter_fichiers(dossier):
    return len(list(dossier.rglob("*.json")))


def test_une_source_en_panne_est_mise_en_sommeil_apres_trois_echecs(
    moteur, tmp_path, serveur_local, monkeypatch
):
    alertes = []
    monkeypatch.setattr(collecte, "envoyer_alerte", alertes.append)
    serveur_local["code"] = 503
    declarer_source(moteur, tmp_path, serveur_local["url"])
    dossier = tmp_path / "bruts"

    for passage in range(1, 4):
        totaux = collecter_tout(moteur, dossier, attente_initiale=0)
        assert totaux["echec"] == 1
        assert lire_source(moteur, "Le Monde")["echecs_consecutifs"] == passage

    source = lire_source(moteur, "Le Monde")
    assert not source["actif"]
    assert totaux["en_sommeil"] == 1
    assert len(alertes) == 1 and "Le Monde" in alertes[0]
    # Trois passages de trois tentatives chacun (le 503 est réessayé avec attente croissante).
    assert len(serveur_local["requetes"]) == 9

    # Une source en sommeil n'est plus interrogée.
    collecter_tout(moteur, dossier, attente_initiale=0)
    assert len(serveur_local["requetes"]) == 9


def test_deux_passages_sur_la_meme_fixture_ne_creent_aucun_doublon(moteur, tmp_path, serveur_local):
    serveur_local["corps"] = FLUX_LE_MONDE
    declarer_source(moteur, tmp_path, serveur_local["url"])
    dossier = tmp_path / "bruts"

    premier = collecter_tout(moteur, dossier, attente_initiale=0)
    second = collecter_tout(moteur, dossier, attente_initiale=0)

    assert (premier["recus"], premier["ecrits"], premier["ignores"]) == (3, 3, 0)
    assert (second["recus"], second["ecrits"], second["ignores"]) == (3, 0, 3)
    assert compter_fichiers(dossier) == 3
    assert lire_source(moteur, "Le Monde")["derniere_reussite"] is not None


def test_le_collecteur_envoie_user_agent_et_en_tetes_conditionnels(moteur, tmp_path, serveur_local):
    serveur_local["corps"] = FLUX_LE_MONDE
    serveur_local["entetes"] = {"ETag": '"v1"', "Last-Modified": "Thu, 12 Nov 2026 14:00:00 GMT"}
    declarer_source(moteur, tmp_path, serveur_local["url"])

    collecter_tout(moteur, tmp_path / "bruts", attente_initiale=0)
    second = collecter_tout(moteur, tmp_path / "bruts", attente_initiale=0)

    premiere_requete, seconde_requete = serveur_local["requetes"]
    assert premiere_requete["User-Agent"] == USER_AGENT
    assert "If-None-Match" not in premiere_requete
    assert seconde_requete["If-None-Match"] == '"v1"'
    assert seconde_requete["If-Modified-Since"] == "Thu, 12 Nov 2026 14:00:00 GMT"
    assert second["non_modifie"] == 1
    assert lire_source(moteur, "Le Monde")["etag"] == '"v1"'


def test_un_404_n_est_pas_reessaye_mais_compte_comme_un_echec(moteur, tmp_path, serveur_local):
    serveur_local["code"] = 404
    declarer_source(moteur, tmp_path, serveur_local["url"])

    totaux = collecter_tout(moteur, tmp_path / "bruts", attente_initiale=0)

    assert totaux["echec"] == 1
    assert len(serveur_local["requetes"]) == 1
    assert lire_source(moteur, "Le Monde")["echecs_consecutifs"] == 1


def test_un_flux_illisible_compte_comme_un_echec(moteur, tmp_path, serveur_local):
    serveur_local["corps"] = b"<html><body>Page de maintenance</body>"
    declarer_source(moteur, tmp_path, serveur_local["url"])

    totaux = collecter_tout(moteur, tmp_path / "bruts", attente_initiale=0)

    assert totaux["echec"] == 1
    assert lire_source(moteur, "Le Monde")["echecs_consecutifs"] == 1
