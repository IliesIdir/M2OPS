"""Point d'entrée d'Alembic : applique les migrations sur la base de DATABASE_URL."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Les tests passent leur propre URL (SQLite) ; sinon on lit DATABASE_URL.
url = config.get_main_option("sqlalchemy.url") or os.environ["DATABASE_URL"]

moteur = create_engine(url)
with moteur.connect() as connexion:
    context.configure(connection=connexion, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()
