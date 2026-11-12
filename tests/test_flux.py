"""Tests du téléchargement et du parseur de flux, sur un vrai flux enregistré."""

import json
from pathlib import Path

import httpx
import pytest

from gazette.flux import (
    USER_AGENT,
    nettoyer_payload,
    parser_flux,
    premiere_rubrique,
    telecharger_flux,
)

FIXTURES = Path(__file__).parent / "fixtures"


def lire_fixture(nom: str) -> bytes:
    return (FIXTURES / nom).read_bytes()


def test_parser_flux_lit_les_trois_items_du_monde():
    items = parser_flux(lire_fixture("flux_le_monde.xml"), "Le Monde")

    assert len(items) == 3
    premier = items[0]
    assert premier["source"] == "Le Monde"
    assert premier["lien"].startswith("https://www.lemonde.fr/economie/article/2026/11/12/")
    assert premier["titre"].startswith("Jensen Huang")
    assert premier["resume"] != ""
    assert premier["publie_le"] == "Thu, 12 Nov 2026 14:53:07 +0100"


def test_parser_flux_ne_garde_ni_images_ni_credits_ni_auteurs():
    items = parser_flux(lire_fixture("flux_le_monde.xml"), "Le Monde")

    for item in items:
        cles = item["payload"].keys()
        assert not any(cle.startswith(("media_", "credit", "author", "content")) for cle in cles)
        assert "links" not in cles


def test_les_items_sont_serialisables_en_json():
    items = parser_flux(lire_fixture("flux_le_monde.xml"), "Le Monde")

    texte = json.dumps(items, ensure_ascii=False)
    assert "Jensen Huang" in texte


def test_un_item_sans_lien_est_ignore():
    flux = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
    <item><title>Sans lien</title></item>
    <item><title>Avec lien</title><link>https://exemple.fr/a</link></item>
    </channel></rss>"""

    items = parser_flux(flux, "Exemple")

    assert [item["titre"] for item in items] == ["Avec lien"]


def test_parser_flux_lit_aussi_atom():
    flux = b"""<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom"><title>t</title>
    <entry><title>Un titre Atom</title><link href="https://exemple.fr/atom"/>
    <updated>2026-11-12T10:00:00Z</updated><summary>Un extrait</summary></entry></feed>"""

    items = parser_flux(flux, "Exemple")

    assert items[0]["lien"] == "https://exemple.fr/atom"
    assert items[0]["publie_le"] == "2026-11-12T10:00:00Z"
    assert items[0]["resume"] == "Un extrait"


def test_nettoyer_payload_retire_les_champs_interdits():
    entree = {"title": "t", "author": "Une personne", "media_content": [], "published_parsed": 1}

    assert nettoyer_payload(entree) == {"title": "t"}


def test_premiere_rubrique():
    assert premiere_rubrique({"tags": [{"term": "Sport"}, {"term": "Foot"}]}) == "Sport"
    assert premiere_rubrique({}) is None


def test_telecharger_flux_envoie_notre_user_agent():
    recu = {}

    def repondre(requete: httpx.Request) -> httpx.Response:
        recu["user_agent"] = requete.headers["User-Agent"]
        return httpx.Response(200, content=b"<rss></rss>")

    client = httpx.Client(
        transport=httpx.MockTransport(repondre), headers={"User-Agent": USER_AGENT}
    )

    assert telecharger_flux(client, "https://exemple.fr/rss") == b"<rss></rss>"
    assert recu["user_agent"] == USER_AGENT


def test_telecharger_flux_leve_une_erreur_sur_un_code_http_en_erreur():
    client = httpx.Client(transport=httpx.MockTransport(lambda requete: httpx.Response(404)))

    with pytest.raises(httpx.HTTPStatusError):
        telecharger_flux(client, "https://exemple.fr/absent")
