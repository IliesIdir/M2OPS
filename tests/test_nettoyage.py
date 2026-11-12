"""Tests du nettoyage : des items bruts vers articles_propres et rejets."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text

from gazette.nettoyage import lister_nouveaux_bruts, nettoyer, normaliser_item
from gazette.regles import charger_regles
from gazette.sources import synchroniser_sources
from gazette.stockage_brut import chemin_item, ecrire_item

RACINE = Path(__file__).parent.parent
REGLES = charger_regles(RACINE / "config" / "regles.toml")
MAINTENANT = datetime.now(UTC)


def item_brut(source: str, lien: str, titre: str, age_heures: float = 1, **autres) -> dict:
    publie_le = (MAINTENANT - timedelta(hours=age_heures)).strftime("%a, %d %b %Y %H:%M:%S +0000")
    return {
        "source": source,
        "lien": lien,
        "titre": titre,
        "resume": autres.get("resume", "Un extrait court."),
        "publie_le": publie_le,
        "rubrique": autres.get("rubrique"),
        "payload": {},
    }


@pytest.fixture
def bruts(moteur, tmp_path):
    """Écrit quelques items bruts tirés des pollueurs observés, et déclare les vraies sources."""
    synchroniser_sources(moteur, RACINE / "sources.csv")
    dossier = tmp_path / "bruts"
    items = [
        item_brut("Le Monde", "https://m/1", "Présidentielle 2027 : le grand oral des candidats"),
        item_brut(
            "La Dépêche du Midi", "https://d/1", "Loto : il découvre qu'il a gagné le jackpot"
        ),
        item_brut("L'Est Républicain", "https://e/1", "Vidéo. $content.TitleNoTags"),
        item_brut(
            "La Dépêche du Midi", "https://d/2", "CARTE. Prix des carburants", age_heures=24 * 56
        ),
        # La même dépêche reprise par deux titres du groupe EBRA : on garde la première publiée.
        item_brut(
            "Le Progrès", "https://p/1", "Social. Le ministre met la pression au patronat", 2
        ),
        item_brut(
            "L'Est Républicain", "https://e/2", "Social. Le ministre met la pression au patronat", 1
        ),
        item_brut(
            "La Provence",
            "https://pr/1",
            "&Eacute;pisode m&eacute;diterran&eacute;en&nbsp;: routes coup&eacute;es",
            resume="<p>Plus de <b>100 mm</b> de pluie.</p>",
        ),
    ]
    recupere_le = MAINTENANT.isoformat()
    for item in items:
        ecrire_item(dossier, item, recupere_le)
    return dossier


def lire_table(moteur, table: str) -> list[dict]:
    with moteur.connect() as connexion:
        return [dict(ligne._mapping) for ligne in connexion.execute(text(f"SELECT * FROM {table}"))]


def test_normaliser_item():
    brut = {
        "id": "abc",
        "source": "La Provence",
        "lien": "https://pr/1",
        "titre": "&Eacute;pisode m&eacute;diterran&eacute;en",
        "resume": "<p>Plus de <b>100 mm</b> de pluie.</p>",
        "publie_le": "2026-11-12T15:08:01+01:00",
        "recupere_le": "2026-11-12T14:30:00+00:00",
        "rubrique": "Région Premium",
    }

    article = normaliser_item(brut)

    assert article["titre"] == "Épisode méditerranéen"
    assert article["resume"] == "Plus de 100 mm de pluie."
    assert article["publie_le"] == datetime(2026, 11, 12, 14, 8, 1, tzinfo=UTC)
    assert article["rubrique"] == "Région Premium"


def test_nettoyer_garde_et_rejette_avec_la_bonne_regle(moteur, bruts):
    resultat = nettoyer(moteur, bruts, REGLES, passage_id="passage-1")

    assert (resultat["entres"], resultat["gardes"], resultat["rejetes"]) == (7, 3, 4)
    assert resultat["par_regle"] == {
        "R09_jeux": 1,
        "R01_titre_vide": 1,
        "R05_trop_ancien": 1,
        "R10_doublon": 1,
    }
    rejets = {ligne["lien"]: ligne["regle"] for ligne in lire_table(moteur, "rejets")}
    assert rejets["https://e/2"] == "R10_doublon"
    gardes = {ligne["lien"] for ligne in lire_table(moteur, "articles_propres")}
    assert gardes == {"https://m/1", "https://p/1", "https://pr/1"}
    assert resultat["par_source"]["L'Est Républicain"] == {"entres": 2, "rejetes": 2}


def test_deux_passages_ne_retraitent_pas_les_memes_items(moteur, bruts):
    nettoyer(moteur, bruts, REGLES, passage_id="passage-1")

    second = nettoyer(moteur, bruts, REGLES, passage_id="passage-2")

    assert second["entres"] == 0
    assert len(lire_table(moteur, "articles_propres")) == 3
    assert len(lire_table(moteur, "rejets")) == 4


def test_un_nouvel_item_repris_d_un_article_deja_garde_est_un_doublon(moteur, bruts):
    nettoyer(moteur, bruts, REGLES, passage_id="passage-1")
    ecrire_item(
        bruts,
        item_brut("Le Figaro", "https://f/1", "Présidentielle 2027 : le grand oral des candidats"),
        MAINTENANT.isoformat(),
    )

    second = nettoyer(moteur, bruts, REGLES, passage_id="passage-2")

    assert second["par_regle"] == {"R10_doublon": 1}


def test_tracabilite_de_l_article_propre_vers_le_brut_et_la_source(moteur, bruts):
    nettoyer(moteur, bruts, REGLES, passage_id="passage-1")

    article = next(a for a in lire_table(moteur, "articles_propres") if a["lien"] == "https://m/1")

    assert chemin_item(bruts, article["source"], article["id"]).exists()
    assert article["passage_id"] == "passage-1"
    assert lister_nouveaux_bruts(bruts, {article["id"]}) != []
