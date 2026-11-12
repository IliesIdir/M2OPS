# La gazette

Projet étudiant du module M2Ops (M2 Data Engineering & IA, EFREI). Chaque matin, un pipeline lit les flux RSS de journaux régionaux et nationaux, écarte ce qui n'a rien à faire dans une gazette, regroupe les articles par thèmes et publie à 7 h l'édition du jour.

Le cadrage (besoin, sources, choix d'outils, risques, architecture) est dans [docs/cadrage.md](docs/cadrage.md).

## Prérequis

- Git
- Docker avec Docker Compose (sous Windows : dans WSL 2)
- uv, seulement pour lancer les tests en local : https://docs.astral.sh/uv/

## Lancer

```bash
git clone https://github.com/IliesIdir/M2OPS.git
cd M2OPS
bin/dev
```

`bin/dev` crée `.env` à partir de `.env.example` s'il n'existe pas (avec un mot de passe aléatoire), construit l'image et démarre les conteneurs :

| Service | Rôle |
|---|---|
| `postgres` | base de la gazette et base séparée de Dagster |
| `preparation` | applique les migrations Alembic et recopie `sources.csv` dans la table `sources`, puis s'arrête |
| `dagster-webserver` | interface de Dagster sur http://localhost:3000 |
| `dagster-daemon` | lance la collecte toutes les 30 minutes |

La collecte écrit un fichier JSON par item dans `articles_bruts/`. Le détail des données est dans [docs/donnees.md](docs/donnees.md).

Commandes utiles :

```bash
docker compose ps
docker compose logs -f dagster-daemon
docker compose exec dagster-daemon python -m gazette collecter
docker compose exec postgres psql -U gazette -d gazette -c "SELECT nom, actif, echecs_consecutifs, derniere_reussite FROM sources ORDER BY nom"
docker compose down
```

En cas de problème, voir [docs/runbook.md](docs/runbook.md).

## Tester

```bash
bin/test
```

Lance le lint (ruff) puis les tests (pytest), comme la CI. Des arguments peuvent être passés à pytest, par exemple `bin/test -k flux`.

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md) : une branche par sujet, des commits au format `type: description`, une pull request avec la CI verte avant tout merge sur `main`. La stratégie CI/CD est décrite dans [docs/ci-cd.md](docs/ci-cd.md).

## Arborescence

| Dossier | Contenu |
|---|---|
| `src/gazette/` | code du pipeline |
| `tests/` | tests, avec `tests/fixtures/` pour les flux enregistrés |
| `docs/` | documentation du projet |
| `infra/` | configuration de l'infrastructure |
| `bin/` | scripts `dev` et `test` |
| `articles_bruts/` | stockage brut (non versionné) |
