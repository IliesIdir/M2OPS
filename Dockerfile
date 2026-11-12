# Image de la gazette en deux étapes : on installe les dépendances avec uv dans une image
# de construction, puis on ne copie que l'environnement virtuel dans une image finale slim.

FROM ghcr.io/astral-sh/uv:0.9.5-python3.12-bookworm-slim AS construction

WORKDIR /app
# On compile le bytecode à l'installation pour un démarrage plus rapide, et on copie les
# fichiers au lieu de faire des liens car le cache uv ne passe pas dans l'image finale.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

# On installe d'abord les seules dépendances : cette couche reste en cache tant que uv.lock ne change pas.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable


FROM python:3.12-slim-bookworm AS finale

ENV DAGSTER_HOME=/opt/dagster/dagster_home

# On fait tourner l'application avec un utilisateur sans droits d'administration.
# Le dossier storage de Dagster (journaux des passages) doit lui appartenir.
RUN useradd --create-home --uid 1000 gazette \
    && mkdir -p "$DAGSTER_HOME/storage" \
    && chown -R gazette:gazette /opt/dagster

WORKDIR /app
COPY --from=construction --chown=gazette:gazette /app/.venv /app/.venv
COPY --chown=gazette:gazette sources.csv alembic.ini ./
COPY --chown=gazette:gazette migrations ./migrations
COPY --chown=gazette:gazette config ./config
COPY --chown=gazette:gazette infra/dagster/dagster.yaml infra/dagster/workspace.yaml $DAGSTER_HOME/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER gazette
CMD ["python", "-m", "gazette", "--help"]
