"""Tests des règles d'exclusion, sur les pollueurs relevés dans les vraies données."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from gazette.normalisation import titre_pour_comparaison
from gazette.regles import (
    ORDRE_DES_REGLES,
    charger_regles,
    encodage_casse,
    regle_de_doublon,
    regle_de_rejet,
    regle_mots_cles,
    titre_invalide,
)

REGLES = charger_regles(Path(__file__).parent.parent / "config" / "regles.toml")
RECUPERE_LE = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)


def article(
    titre: str,
    rubrique: str | None = None,
    age_heures: float = 1,
    lien: str = "https://exemple.fr/a",
) -> dict:
    return {
        "titre": titre,
        "lien": lien,
        "rubrique": rubrique,
        "publie_le": RECUPERE_LE - timedelta(hours=age_heures),
        "recupere_le": RECUPERE_LE,
    }


def test_toutes_les_regles_du_fichier_sont_dans_l_ordre_d_application():
    for regle in REGLES["mots_cles"]:
        assert regle["id"] in ORDRE_DES_REGLES


def test_titre_invalide():
    assert titre_invalide("", REGLES)
    assert titre_invalide("Vidéo", REGLES)
    assert titre_invalide("Vidéo. $content.TitleNoTags", REGLES)
    assert not titre_invalide("Présidentielle 2027 : le grand oral des candidats", REGLES)


def test_encodage_casse():
    assert encodage_casse("La rÃ©forme")
    assert not encodage_casse("La réforme")


def test_regle_mots_cles_par_motif_et_par_rubrique():
    publi = next(r for r in REGLES["mots_cles"] if r["id"] == "R06_publi")
    jeux = next(r for r in REGLES["mots_cles"] if r["id"] == "R09_jeux")

    assert regle_mots_cles(
        article("Nailloux Outlet Village : Black Friday dès le 16 novembre"), publi
    )
    assert regle_mots_cles(article("Il découvre qu'il a gagné", "Loto - EuroMillions"), jeux)
    assert not regle_mots_cles(article("Le RN veut gagner les municipales"), jeux)


@pytest.mark.parametrize(
    "titre, rubrique, attendu",
    [
        ("Vidéo. $content.TitleNoTags", "Faits-divers", "R01_titre_vide"),
        ("La Dépêche du Midi lance son espace jeux : à vos neurones", None, "R09_jeux"),
        (
            "Loto : il découvre plusieurs semaines après le tirage",
            "Loto - EuroMillions",
            "R09_jeux",
        ),
        ("Black Friday dès le 16 novembre avec des remises jusqu'à 70 %", "Commerces", "R06_publi"),
        ("Votre horoscope du jour pour le Bélier", None, "R07_horoscope"),
        ("Bruno Retailleau pousse pour une primaire", "Politique", None),
        ("Jeux de la jeunesse : le sport mixte à l'épreuve", None, None),
        ("Tempête Charles : la recette du succès des secours", None, None),
    ],
)
def test_pollueurs_observes(titre, rubrique, attendu):
    assert regle_de_rejet(article(titre, rubrique), [], REGLES) == attendu


def test_une_recette_est_reconnue_par_son_lien():
    recette = article(
        "Le cake au citron et au pavot : la recette de Pascale Weeks",
        lien="https://www.lemonde.fr/les-recettes-du-monde/article/2026/11/12/le-cake.html",
    )

    assert regle_de_rejet(recette, [], REGLES) == "R08_service"


def test_dates_futures_anciennes_ou_absentes():
    assert regle_de_rejet(article("Un titre d'actualité normal", age_heures=-1), [], REGLES) == (
        "R04_date_future"
    )
    # Page évergreen de La Dépêche, publiée en septembre et toujours dans le flux en novembre.
    assert regle_de_rejet(
        article("CARTE. Prix des carburants", age_heures=24 * 56), [], REGLES
    ) == ("R05_trop_ancien")
    sans_date = {**article("Un titre d'actualité normal"), "publie_le": None}
    assert regle_de_rejet(sans_date, [], REGLES) == "R03_sans_date"
    # Quelques minutes d'avance d'horloge chez l'éditeur sont tolérées.
    assert (
        regle_de_rejet(article("Un titre d'actualité normal", age_heures=-0.1), [], REGLES) is None
    )


def test_doublon_exact_et_proche():
    gardes = [
        titre_pour_comparaison("Politique. Écrits antisémites : Jordan Bardella a porté plainte")
    ]

    # Même dépêche reprise à l'identique par deux titres du même groupe.
    assert regle_de_doublon(
        "Politique. Écrits antisémites : Jordan Bardella a porté plainte", gardes, REGLES
    ) == ("R10_doublon")
    # Même titre à un mot près.
    assert regle_de_doublon(
        "Politique. Écrits antisémites : Jordan Bardella a bien porté plainte", gardes, REGLES
    ) == ("R11_doublon_proche")
    # Même sujet, autre article : on le garde, le regroupement par thèmes s'en chargera.
    assert (
        regle_de_doublon(
            "Ecrits antisémites : Jordan Bardella porte plainte pour faux et usage de faux",
            gardes,
            REGLES,
        )
        is None
    )
