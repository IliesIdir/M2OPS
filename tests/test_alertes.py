"""Tests de l'envoi des alertes Discord, sans appeler Discord."""

import httpx

from gazette import alertes
from gazette.alertes import envoyer_alerte


def test_sans_webhook_l_alerte_reste_dans_les_journaux(monkeypatch, caplog):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)

    assert envoyer_alerte("source en panne") is False
    assert "source en panne" in caplog.text


def test_avec_webhook_le_message_est_poste(monkeypatch):
    envoyes = []

    def faux_post(url, json, timeout):
        envoyes.append((url, json))
        return httpx.Response(204, request=httpx.Request("POST", url))

    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/webhook")
    monkeypatch.setattr(alertes.httpx, "post", faux_post)

    assert envoyer_alerte("source en panne") is True
    assert envoyes == [("https://discord.test/webhook", {"content": "[gazette] source en panne"})]


def test_un_webhook_en_erreur_ne_fait_pas_planter_le_pipeline(monkeypatch):
    def faux_post(url, json, timeout):
        return httpx.Response(500, request=httpx.Request("POST", url))

    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/webhook")
    monkeypatch.setattr(alertes.httpx, "post", faux_post)

    assert envoyer_alerte("source en panne") is False
