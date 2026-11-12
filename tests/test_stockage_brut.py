"""Tests du stockage brut : un fichier par item, jamais écrit deux fois."""

import json

from gazette.stockage_brut import chemin_item, ecrire_item, identifiant_item

ITEM = {
    "source": "Le Monde",
    "lien": "https://www.lemonde.fr/a.html",
    "titre": "Un titre",
    "resume": "Un extrait",
    "publie_le": "Thu, 12 Nov 2026 14:53:07 +0100",
    "rubrique": None,
    "payload": {"title": "Un titre"},
}


def test_identifiant_stable_et_propre_a_la_source_et_au_lien():
    assert identifiant_item("Le Monde", "https://a") == identifiant_item("Le Monde", "https://a")
    assert identifiant_item("Le Monde", "https://a") != identifiant_item("Le Monde", "https://b")
    assert identifiant_item("Le Monde", "https://a") != identifiant_item("Libération", "https://a")
    assert len(identifiant_item("Le Monde", "https://a")) == 16


def test_ecrire_item_cree_un_fichier_avec_tous_les_champs(tmp_path):
    assert ecrire_item(tmp_path, ITEM, "2026-11-12T14:00:00+00:00") is True

    identifiant = identifiant_item("Le Monde", ITEM["lien"])
    chemin = chemin_item(tmp_path, "Le Monde", identifiant)
    assert chemin.parent.name == "le-monde"
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    assert list(contenu) == [
        "id",
        "source",
        "lien",
        "titre",
        "resume",
        "publie_le",
        "recupere_le",
        "rubrique",
        "payload",
    ]
    assert contenu["id"] == identifiant
    assert contenu["recupere_le"] == "2026-11-12T14:00:00+00:00"


def test_ecrire_item_n_ecrase_pas_un_item_existant(tmp_path):
    ecrire_item(tmp_path, ITEM, "2026-11-12T14:00:00+00:00")

    assert ecrire_item(tmp_path, {**ITEM, "titre": "Modifié"}, "2026-11-12T15:00:00+00:00") is False

    chemin = chemin_item(tmp_path, "Le Monde", identifiant_item("Le Monde", ITEM["lien"]))
    assert json.loads(chemin.read_text(encoding="utf-8"))["titre"] == "Un titre"
