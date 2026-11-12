# Stratégie CI/CD

## La stratégie en dix lignes

1. `main` est toujours déployable : on n'y pousse jamais directement, tout passe par une pull request.
2. Une branche par TD ou par sujet (`td3-collecte`, `fix-dates-provence`...).
3. Chaque push, sur n'importe quelle branche, déclenche `.github/workflows/ci.yml`.
4. Job `lint-et-tests` : `bin/test`, le même script qu'en local (ruff check, ruff format --check, pytest).
5. Job `image` : construit l'image Docker (Dockerfile multi-étapes, base slim, utilisateur non root).
6. Sur `main` seulement, l'image est poussée sur ghcr.io avec le tag `YYYYMMDDHHMMSS-sha` (heure UTC du build, sha court du commit) : on sait toujours de quel commit vient une image.
7. Sur les autres branches, donc pour une pull request, l'image est construite mais pas poussée.
8. La protection de `main` exige une pull request et les deux jobs verts avant le merge : une CI rouge bloque.
9. Les secrets ne sont jamais dans le dépôt : `.env` en local (ignoré par Git), `GITHUB_TOKEN` fourni par GitHub en CI.
10. Pas encore de déploiement automatique : il arrive avec l'infrastructure de production (TD 7).

## Protection de main

La commande est rejouable ; elle demande la CLI `gh` connectée avec un compte administrateur du dépôt :

```bash
gh api -X PUT repos/IliesIdir/M2OPS/branches/main/protection --input infra/github/protection-main.json
```

Le fichier `infra/github/protection-main.json` exige les contrôles `lint-et-tests` et `image`, une pull request (sans approbation obligatoire, l'équipe pouvant être réduite), et s'applique aussi aux administrateurs. Les contrôles ne sont proposés par GitHub qu'après avoir tourné une première fois sur le dépôt.

Vérification :

```bash
gh api repos/IliesIdir/M2OPS/branches/main/protection --jq '.required_status_checks.contexts'
```

## Preuve qu'une CI rouge bloque

Essai fait le 12/11/2026 :

| Etape | Résultat |
|---|---|
| Branche `ci-rouge-preuve` créée depuis `td2-socle` (CI verte, run 43243712672) | |
| Test `test_parser_flux_lit_les_trois_items_du_monde` cassé exprès (`== 4` au lieu de `== 3`), commit `3f21f00` poussé | |
| CI déclenchée par le push (run 43244674223) | job `lint-et-tests` en échec à l'étape "Lint et tests" |
| Job `image` | non lancé (`skipped`), car il dépend de `lint-et-tests` : aucune image n'est construite ni publiée |
| Branche supprimée (locale et distante) | |

Avec la protection de `main` active, une pull request depuis cette branche n'aurait pas pu être mergée : les contrôles requis `lint-et-tests` et `image` n'étaient pas verts.

## Mesures

Le temps entre un commit et une édition qui l'utilise sera mesuré quand le déploiement sera automatisé (TD 7).
