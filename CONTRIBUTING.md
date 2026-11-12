# Contribuer à La gazette

## Branches

- `main` est toujours déployable. Personne n'y pousse directement : la protection de branche l'interdit.
- Une branche par TD ou par sujet, nommée en minuscules avec des tirets : `td3-collecte`, `fix-dates-provence`, `docs-runbook`.
- On part toujours de `main` à jour : `git switch main && git pull && git switch -c ma-branche`.

## Commits

- En français, au format `type: description courte`, sans majuscule ni point final.
- Types : `feat` (fonctionnalité), `fix` (correction), `test`, `docs`, `ci`, `chore` (outillage, dépendances).
- Exemple : `feat: ajoute la mise en sommeil des sources en échec`.
- Des commits petits et réguliers, qui passent `bin/test`.
- Aucun secret dans un commit : les valeurs vont dans `.env`, les noms de variables dans `.env.example`.

## Avant d'ouvrir une pull request

- `bin/test` passe en local.
- Chaque fonction nouvelle ou modifiée a son test.
- La documentation de `docs/` est à jour avec le code.
- Une nouvelle dépendance est justifiée dans `docs/cadrage.md` (le choix, deux alternatives, pourquoi pas elles).

## Revue et merge

- Toute modification passe par une pull request vers `main`.
- Un autre membre de l'équipe relit la pull request (même rapidement) : il clone la branche, lance `bin/test` et `bin/dev`, et laisse un commentaire.
- Le merge n'est possible que si les contrôles `lint-et-tests` et `image` sont verts.
- C'est l'auteur de la pull request qui merge, après la relecture et la CI verte. On supprime la branche après le merge.
