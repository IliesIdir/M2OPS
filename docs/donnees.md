# Données de la gazette

Dictionnaire des champs et contrat de données, du flux de l'éditeur jusqu'aux articles propres.

## Table `sources` (PostgreSQL, migration `migrations/versions/0001_table_sources.py`)

Une ligne par source de `sources.csv`. La table est remplie par `python -m gazette synchroniser-sources`, lancé à chaque démarrage par le service `preparation`.

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `nom` | text, clé primaire | oui | Nom de la source, identique à la colonne `nom` de `sources.csv` |
| `type` | text | oui | `PQR` ou `PQN` (contrainte `type_pqr_ou_pqn`) |
| `url_flux` | text | oui | Adresse du flux RSS, colonne `acces` de `sources.csv` |
| `actif` | boolean, défaut `true` | oui | `false` si la source est en sommeil (3 échecs de suite) ou retirée de `sources.csv` |
| `derniere_reussite` | timestamptz | non | Date UTC de la dernière collecte réussie (200 ou 304) |
| `echecs_consecutifs` | integer, défaut 0 | oui | Nombre d'échecs de suite, remis à 0 à chaque réussite |
| `etag` | text | non | En-tête `ETag` de la dernière réponse, renvoyé en `If-None-Match` |
| `last_modified` | text | non | En-tête `Last-Modified` de la dernière réponse, renvoyé en `If-Modified-Since` |

Règles de mise à jour :

- Une source nouvelle dans `sources.csv` est créée active.
- Une source déjà connue garde son état (`actif`, `echecs_consecutifs`, `derniere_reussite`). Si son adresse change, `etag` et `last_modified` sont remis à vide.
- Une source retirée de `sources.csv` passe à `actif = false` ; son historique est conservé.
- Une source en sommeil se réveille avec `python -m gazette reactiver-source "<nom>"` (voir le runbook).

## Items bruts (`articles_bruts/`)

Un fichier JSON par item : `articles_bruts/<source>/<id>.json`, où `<source>` est le nom de la source sans accent ni espace (`le-monde`, `la-depeche-du-midi`). Le fichier est écrit une seule fois et n'est jamais modifié.

| Champ | Type JSON | Description |
|---|---|---|
| `id` | chaîne de 16 caractères hexadécimaux | Début du SHA-256 de `"<source>\|<lien>"`. Clé naturelle (source, lien) : un même lien d'une même source donne toujours le même identifiant, donc le même fichier |
| `source` | chaîne | Nom de la source (table `sources`) |
| `lien` | chaîne | URL de l'article (`link` du flux) |
| `titre` | chaîne | Titre tel que reçu (`title`), entités HTML et encodage non corrigés |
| `resume` | chaîne | Extrait tel que reçu (`description` en RSS, `summary` en Atom), peut contenir du HTML |
| `publie_le` | chaîne ou null | Date de publication telle que reçue (`pubDate` ou `updated`) : RFC 822 ou ISO 8601 selon l'éditeur. Convertie en UTC au nettoyage |
| `recupere_le` | chaîne ISO 8601 UTC | Date de la collecte qui a écrit l'item |
| `rubrique` | chaîne ou null | Première catégorie de l'item (`category`), si l'éditeur en donne |
| `payload` | objet | Entrée complète du flux telle que lue par feedparser, sans les champs interdits (voir plus bas) |

Champs retirés du `payload` avant écriture, pour respecter le bornage :

| Champs | Raison |
|---|---|
| `author*`, `contributor*`, `publisher*`, `credit`, `media_credit` | Noms de personnes (auteurs, crédits photo) : données personnelles |
| `content` | Peut contenir le texte intégral de l'article |
| `media_*`, `image`, `links`, `href` | Images et liens vers des images |
| `comments` | Lien vers les commentaires |
| `*_parsed` | Dates déjà converties par feedparser, non sérialisables en JSON (la date reste dans `published`) |

Idempotence : le fichier est ouvert en mode création exclusive (`"x"`). Si l'item existe déjà, rien n'est écrit et l'item est compté comme ignoré. Deux passages sur le même flux ne créent donc aucun doublon (test `test_deux_passages_sur_la_meme_fixture_ne_creent_aucun_doublon`).

## Journaux de la collecte

Une ligne JSON par source et par passage, visible dans les journaux du daemon Dagster et dans l'interface (onglet du passage) :

```json
{"evenement": "collecte_source", "source": "Le Monde", "recus": 16, "ecrits": 3, "statut": "ok", "ignores": 13, "duree_s": 0.08}
```

| Champ | Description |
|---|---|
| `statut` | `ok` (200), `non_modifie` (304), `echec` (après reprises) |
| `recus` | Items lus dans le flux |
| `ecrits` | Items nouveaux écrits dans `articles_bruts/` |
| `ignores` | Items déjà présents (`recus - ecrits`) |
| `duree_s` | Durée de la collecte de la source, reprises comprises |
| `erreur`, `mise_en_sommeil` | Présents en cas d'échec |

Une ligne `collecte_terminee` donne les totaux du passage ; les mêmes compteurs sont publiés en métadonnées de l'asset `articles_bruts` dans Dagster.

## Table `articles_propres` (migration `0002_articles_propres_et_rejets.py`)

Les articles gardés après normalisation et règles d'exclusion, alimentés à chaque passage par l'asset Dagster `articles_propres`.

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `id` | text, clé primaire | oui | Identifiant de l'item brut (nom du fichier dans `articles_bruts/<source>/`) |
| `source` | text, clé étrangère vers `sources.nom` | oui | Source de l'article |
| `lien` | text | oui | URL de l'article ; couple (`source`, `lien`) unique |
| `titre` | text | oui | Titre normalisé : sans HTML, entités décodées, encodage réparé, espaces simples |
| `resume` | text, défaut `''` | oui | Extrait normalisé, 300 caractères au plus |
| `publie_le` | timestamptz | oui | Date de publication, en UTC |
| `recupere_le` | timestamptz | oui | Date de collecte de l'item brut |
| `rubrique` | text | non | Rubrique de l'éditeur, normalisée |
| `nettoye_le` | timestamptz | oui | Date du passage de nettoyage qui a gardé l'article |
| `passage_id` | text | oui | Identifiant du passage Dagster (run id), ou `manuel` |

## Table `rejets`

Les articles écartés, avec la règle qui les a écartés (voir `docs/qualite.md`).

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `id` | text, clé primaire | oui | Identifiant de l'item brut |
| `source` | text, clé étrangère vers `sources.nom` | oui | Source de l'item |
| `lien` | text | oui | URL de l'item |
| `titre` | text | oui | Titre normalisé (peut être vide, c'est la règle R01) |
| `regle` | text | oui | Identifiant de la règle : `R01_titre_vide` à `R11_doublon_proche` |
| `publie_le` | timestamptz | non | Date de publication en UTC, vide si illisible (règle R03) |
| `recupere_le` | timestamptz | oui | Date de collecte |
| `rejete_le` | timestamptz | oui | Date du passage qui l'a écarté |
| `passage_id` | text | oui | Identifiant du passage Dagster |

Un item brut est traité une seule fois : le nettoyage ne lit que les fichiers dont l'id n'est ni dans `articles_propres` ni dans `rejets`. Tout un passage est écrit dans une seule transaction.

## Contrat de données

| Engagement | Valeur | Où c'est vérifié |
|---|---|---|
| Schéma | Tables ci-dessus, créées uniquement par les migrations Alembic | `migrations/versions/`, test `conftest.py` qui applique les migrations |
| Fraîcheur de la collecte | Chaque source active interrogée toutes les 30 minutes | `derniere_reussite` dans `sources`, planification Dagster |
| Fraîcheur des articles | Un article propre a été publié moins de 24 h avant sa collecte | Règle R05_trop_ancien |
| Dates | En UTC, jamais dans le futur | Normalisation `date_en_utc`, règle R04, contrôle `aucune_date_future` |
| Extrait | 300 caractères au plus | Normalisation `borner_extrait`, contrôle `extraits_bornes` |
| Unicité | Un article par couple (source, lien) | Clé primaire `id`, contrainte `article_unique_par_source_et_lien` |

### Ce qu'on ne stocke pas

- le texte intégral des articles, les images et leurs liens, les commentaires ;
- les noms des auteurs et des photographes (champs retirés du payload brut, jamais repris dans les tables) ;
- aucune donnée sur les lecteurs : la gazette n'a ni comptes, ni abonnés, ni suivi d'audience.

### Rétention

| Données | Durée | Ensuite |
|---|---|---|
| Items bruts (`articles_bruts/`) | 90 jours après `recupere_le` | Supprimés : le brut ne sert qu'à rejouer un nettoyage ou à tracer un article |
| `rejets` | 90 jours | Supprimés : ils ne servent qu'à ajuster les règles |
| `articles_propres` | 1 an | Supprimés ; les thèmes et éditions gardent ce qu'il faut pour l'historique |
| Rapports de qualité (`rapports/`) | 1 an | Supprimés |
| Éditions publiées (TD 7) | 1 mois en ligne | Déplacées vers un stockage froid (archive compressée) |
| Historique Dagster | 90 jours | Purgé |

Ces durées sont écrites ici dès maintenant ; la purge automatique sera ajoutée avec l'infrastructure de production.

## Traçabilité

D'un article de l'édition, on remonte jusqu'au flux :

1. `articles_propres.id` donne l'item brut : `articles_bruts/<source sans accent>/<id>.json`, tel que reçu, avec `recupere_le` ;
2. `articles_propres.source` donne la source dans la table `sources`, donc l'adresse du flux (`url_flux`) ;
3. `articles_propres.passage_id` donne le passage Dagster qui l'a gardé, et ses journaux dans l'interface ;
4. pour un article écarté, `rejets.regle` dit quelle règle l'a écarté et pourquoi (`docs/qualite.md`).

Exemple de requête :

```sql
SELECT a.id, a.titre, a.passage_id, s.url_flux
FROM articles_propres a JOIN sources s ON s.nom = a.source
WHERE a.lien = 'https://www.lemonde.fr/...';
```
