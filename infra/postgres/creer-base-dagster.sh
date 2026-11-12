#!/usr/bin/env bash
# Exécuté par l'image postgres au premier démarrage (volume vide) : crée la base de Dagster,
# séparée de la base de la gazette pour que leurs données ne se mélangent pas.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -c "CREATE DATABASE ${DAGSTER_DB} OWNER ${POSTGRES_USER};"
