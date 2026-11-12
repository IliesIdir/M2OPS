# Données de la gazette

Dictionnaire des champs, du flux de l'éditeur jusqu'au stockage brut.

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
