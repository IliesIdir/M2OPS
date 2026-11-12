"""Fixtures partagées : une base de test migrée par Alembic et un faux éditeur HTTP local."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from gazette.base import creer_moteur

RACINE = Path(__file__).parent.parent


@pytest.fixture
def moteur(tmp_path):
    """Base SQLite neuve, créée avec les vraies migrations pour les tester au passage."""
    # On utilise SQLite pour que les tests tournent sans service ; le SQL écrit reste
    # compatible avec PostgreSQL, qui est vérifié en lançant le pipeline dans Docker.
    url = f"sqlite:///{tmp_path / 'test.db'}"
    configuration = Config(str(RACINE / "alembic.ini"))
    configuration.set_main_option("sqlalchemy.url", url)
    command.upgrade(configuration, "head")
    return creer_moteur(url)


@pytest.fixture
def serveur_local():
    """Démarre un serveur HTTP local dont on règle la réponse dans le dictionnaire `etat`."""
    etat = {"code": 200, "corps": b"", "entetes": {}, "requetes": []}

    class Gestionnaire(BaseHTTPRequestHandler):
        def do_GET(self):
            etat["requetes"].append(dict(self.headers))
            # Si le client renvoie le bon ETag, on répond 304 comme un vrai éditeur.
            etag = etat["entetes"].get("ETag")
            code = 304 if etag and self.headers.get("If-None-Match") == etag else etat["code"]
            self.send_response(code)
            for nom, valeur in etat["entetes"].items():
                self.send_header(nom, valeur)
            self.end_headers()
            if code == 200:
                self.wfile.write(etat["corps"])

        def log_message(self, *args):
            pass

    serveur = ThreadingHTTPServer(("127.0.0.1", 0), Gestionnaire)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    etat["url"] = f"http://127.0.0.1:{serveur.server_port}/rss"
    yield etat
    serveur.shutdown()
