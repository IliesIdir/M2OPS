# Runbook

Gestes d'exploitation, un par incident connu. Les commandes se lancent depuis la racine du dépôt.

## Une source est mise en sommeil

Symptôme : une alerte Discord "source mise en sommeil apres 3 echecs consecutifs", ou un avertissement `source_mise_en_sommeil` dans les journaux du daemon.

1. Lire l'erreur de la source dans les journaux :

   ```bash
   docker compose logs dagster-daemon | grep '"statut": "echec"'
   ```

2. Tester le flux à la main, avec notre User-Agent :

   ```bash
   curl -sI -A "gazette-m2ops/0.1 (projet etudiant EFREI M2; +https://github.com/IliesIdir/M2OPS)" "<url du flux>"
   ```

3. Selon la cause :
   - erreur passagère côté éditeur (5xx) : attendre qu'elle disparaisse ;
   - adresse changée : corriger la colonne `acces` dans `sources.csv`, relire robots.txt et les conditions, puis relancer `bin/dev` (la synchronisation met la table à jour) ;
   - flux interdit ou supprimé : retirer la source de `sources.csv` et le noter dans `docs/cadrage.md`.

4. Réveiller la source une fois le problème réglé :

   ```bash
   docker compose exec dagster-daemon python -m gazette reactiver-source "<nom>"
   ```

5. Vérifier au passage suivant que `echecs_consecutifs` est à 0 et que `derniere_reussite` avance.

## La collecte ne tourne plus

1. `docker compose ps` : les services `dagster-daemon` et `dagster-webserver` doivent être `Up`.
2. Dans l'interface (http://localhost:3000), onglet Automation : la planification `collecte_schedule` doit être `Running`.
3. Relancer l'environnement si besoin : `bin/dev`.
