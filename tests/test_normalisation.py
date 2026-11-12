"""Un test par fonction de normalisation, avec des cas vus dans les vrais flux."""

from datetime import UTC, datetime

from gazette.normalisation import (
    borner_extrait,
    date_en_utc,
    decoder_entites,
    normaliser_espaces,
    normaliser_texte,
    reparer_encodage,
    retirer_html,
    similarite_jaccard,
    titre_pour_comparaison,
)


def test_decoder_entites():
    assert decoder_entites("L&#039;&eacute;t&eacute; &amp; l&rsquo;hiver") == "L'été & l’hiver"


def test_retirer_html():
    assert retirer_html("<p>Un <b>extrait</b></p>") == " Un  extrait  "


def test_reparer_encodage():
    assert reparer_encodage("Ã‰lysÃ©e : la rÃ©forme") == "Élysée : la réforme"
    assert reparer_encodage("Élysée") == "Élysée"
    # Un texte qui contient "Â" sans être mal encodé n'est pas abîmé.
    assert reparer_encodage("Â bientôt 😀") == "Â bientôt 😀"


def test_normaliser_espaces():
    assert normaliser_espaces("  Guerre en\u00a0Ukraine\u202f:\n la suite\t ") == (
        "Guerre en Ukraine : la suite"
    )


def test_normaliser_texte_enchaine_les_nettoyages():
    assert normaliser_texte("<p>L&#039;Ã©tÃ©\u00a0arrive</p>") == "L'été arrive"
    assert normaliser_texte(None) == ""


def test_borner_extrait():
    assert borner_extrait("court") == "court"
    extrait = borner_extrait("mot " * 100, longueur_max=20)
    assert extrait == "mot mot mot mot..."
    assert len(extrait) <= 20


def test_date_en_utc_rfc_822_et_iso_8601():
    attendu = datetime(2026, 11, 12, 13, 53, 7, tzinfo=UTC)
    assert date_en_utc("Thu, 12 Nov 2026 14:53:07 +0100") == attendu
    # La Provence publie ses dates en ISO 8601 dans un flux RSS.
    assert date_en_utc("2026-11-12T14:53:07+01:00") == attendu
    assert date_en_utc("2026-11-12T13:53:07Z") == attendu


def test_date_en_utc_cas_limites():
    assert date_en_utc("2026-11-12T13:53:07") == datetime(2026, 11, 12, 13, 53, 7, tzinfo=UTC)
    assert date_en_utc("pas une date") is None
    assert date_en_utc(None) is None


def test_titre_pour_comparaison():
    assert titre_pour_comparaison("Énergie. Carburant : pourquoi ?") == "energie carburant pourquoi"


def test_similarite_jaccard():
    assert similarite_jaccard("a b c d", "a b c d") == 1.0
    assert similarite_jaccard("a b c d", "a b c e") == 0.6
    assert similarite_jaccard("", "a") == 0.0
