"""Tests du rapport de qualité et des contrôles de données."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text

from gazette.qualite import (
    controle_dates_futures,
    controle_extraits_bornes,
    controle_taux_rejet,
    controle_titres_vides,
    ecrire_rapport,
    rapport_du_jour,
    rapport_en_markdown,
)
from gazette.sources import synchroniser_sources

RACINE = Path(__file__).parent.parent
MAINTENANT = datetime.now(UTC)


def inserer(moteur, table: str, **valeurs):
    colonnes = ", ".join(valeurs)
    parametres = ", ".join(f":{nom}" for nom in valeurs)
    with moteur.begin() as connexion:
        connexion.execute(text(f"INSERT INTO {table} ({colonnes}) VALUES ({parametres})"), valeurs)


def article(moteur, id: str, source: str = "Le Monde", **autres):
    valeurs = {
        "id": id,
        "source": source,
        "lien": f"https://exemple.fr/{id}",
        "titre": "Un titre d'actualité",
        "resume": "Un extrait",
        "publie_le": MAINTENANT - timedelta(hours=1),
        "recupere_le": MAINTENANT,
        "nettoye_le": MAINTENANT,
        "passage_id": "p1",
    }
    inserer(moteur, "articles_propres", **{**valeurs, **autres})


def rejet(moteur, id: str, regle: str, source: str = "La Dépêche du Midi", titre: str = "Loto"):
    inserer(
        moteur,
        "rejets",
        id=id,
        source=source,
        lien=f"https://exemple.fr/{id}",
        titre=titre,
        regle=regle,
        recupere_le=MAINTENANT,
        rejete_le=MAINTENANT,
        passage_id="p1",
    )


def test_rapport_du_jour_compte_par_regle_et_par_source(moteur):
    synchroniser_sources(moteur, RACINE / "sources.csv")
    article(moteur, "a1")
    article(moteur, "a2", source="La Dépêche du Midi")
    rejet(moteur, "r1", "R09_jeux")
    rejet(moteur, "r2", "R09_jeux")
    rejet(moteur, "r3", "R05_trop_ancien", source="Le Monde", titre="Vieux")

    rapport = rapport_du_jour(moteur, MAINTENANT.date())

    assert (rapport["entres"], rapport["gardes"], rapport["rejetes"]) == (5, 2, 3)
    assert rapport["par_regle"] == {"R05_trop_ancien": 1, "R09_jeux": 2}
    assert rapport["par_source"]["La Dépêche du Midi"] == {"gardes": 1, "rejetes": 2, "entres": 3}
    assert rapport["rejets_frequents"][0] == {
        "regle": "R09_jeux",
        "source": "La Dépêche du Midi",
        "nombre": 2,
        "exemple": "Loto",
    }
    # Un autre jour n'a rien.
    assert rapport_du_jour(moteur, (MAINTENANT - timedelta(days=2)).date())["entres"] == 0


def test_rapport_en_markdown_et_fichier_archive(moteur, tmp_path):
    synchroniser_sources(moteur, RACINE / "sources.csv")
    article(moteur, "a1")
    rejet(moteur, "r1", "R09_jeux", titre="Loto | EuroMillions")
    rapport = rapport_du_jour(moteur, MAINTENANT.date())

    texte = rapport_en_markdown(rapport)
    chemin = ecrire_rapport(rapport, tmp_path / "rapports")

    assert "taux de rejet 50.0%" in texte
    assert "| R09_jeux | 1 |" in texte
    assert "Loto / EuroMillions" in texte
    assert chemin.name == f"qualite-{MAINTENANT.date().isoformat()}.md"
    assert chemin.read_text(encoding="utf-8") == texte


def test_controles_au_vert_sur_des_donnees_saines(moteur):
    synchroniser_sources(moteur, RACINE / "sources.csv")
    article(moteur, "a1")

    assert controle_dates_futures(moteur, MAINTENANT, 10)["ok"]
    assert controle_titres_vides(moteur)["ok"]
    assert controle_extraits_bornes(moteur)["ok"]


def test_controles_au_rouge_sur_des_donnees_fausses(moteur):
    synchroniser_sources(moteur, RACINE / "sources.csv")
    article(moteur, "a1", publie_le=MAINTENANT + timedelta(days=1))
    article(moteur, "a2", titre="  ")
    article(moteur, "a3", resume="x" * 2000)

    futur = controle_dates_futures(moteur, MAINTENANT, 10)
    assert not futur["ok"] and futur["valeur"] == 1
    assert not controle_titres_vides(moteur)["ok"]
    assert controle_extraits_bornes(moteur)["valeur"] == 2000


def test_controle_taux_rejet():
    rapport = {
        "par_source": {
            "A": {"entres": 20, "gardes": 2, "rejetes": 18},
            "B": {"entres": 20, "gardes": 15, "rejetes": 5},
            # Trop peu d'articles pour juger.
            "C": {"entres": 2, "rejetes": 2},
        }
    }

    resultat = controle_taux_rejet(rapport, taux_max=0.8, entres_min=10)

    assert not resultat["ok"]
    assert resultat["valeur"] == 1
    assert "A" in resultat["detail"]
