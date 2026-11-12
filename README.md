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

`bin/dev` crée `.env` à partir de `.env.example` s'il n'existe pas (avec un mot de passe aléatoire), construit l'image et démarre les conteneurs. Les items lus arrivent dans `articles_bruts/`.

Commandes utiles :

```bash
docker compose ps
docker compose logs -f app
docker compose down
```

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
