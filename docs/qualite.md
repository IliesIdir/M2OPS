# Qualité des données

## Dix pollueurs relevés dans les données brutes

Relevés le 12/11/2026 sur les 346 items du premier passage de collecte.

| N° | Source | Item (titre tel que reçu) | Problème | Règle |
|---|---|---|---|---|
| 1 | L'Est Républicain | « Vidéo. $content.TitleNoTags » | Gabarit de l'éditeur non rempli, pas de vrai titre | R01_titre_vide |
| 2 | La Dépêche du Midi | « Loto : il découvre plusieurs semaines après le tirage qu'il a gagné le jackpot » (rubrique Loto - EuroMillions) | Contenu de loterie | R09_jeux |
| 3 | La Dépêche du Midi | « La Dépêche du Midi lance son espace jeux : à vos neurones, prêts, jouez ! » (publié le 16/10/2025) | Autopromotion des jeux, et vieille d'un an | R05_trop_ancien |
| 4 | La Dépêche du Midi | « Nailloux Outlet Village : Black Friday dès le 16 novembre avec des remises jusqu'à 70 % » | Promotion commerciale | R06_publi |
| 5 | La Dépêche du Midi | « CARTE. Prix des carburants : tarifs, stations et bornes de recharge... » (publié le 17/09/2026) | Page de service mise à jour en continu, date ancienne | R05_trop_ancien |
| 6 | 20 Minutes | « En images : Tous les principaux candidats déclarés à l'élection présidentielle » (publié le 23/10/2025) | Diaporama ancien resté dans le flux | R05_trop_ancien |
| 7 | Le Monde | « Le cake au citron et au pavot : la recette de Pascale Weeks » | Recette, pas d'actualité | R08_service |
| 8 | L'Est Républicain et Le Progrès | « Énergie. Carburant : pourquoi certaines stations du nord-est de la France rencontrent des difficultés » | Même dépêche publiée mot pour mot par deux titres du groupe EBRA | R10_doublon |
| 9 | L'Est Républicain et Le Progrès | « Politique. Écrits antisémites : Jordan Bardella a porté plainte pour faux et usage de faux » | Idem, 6 dépêches en double au total | R10_doublon |
| 10 | La Provence | Dates en ISO 8601 (`2026-11-12T15:08:01+01:00`) dans un flux RSS 2.0, qui attend du RFC 822 | Format de date non conforme | Normalisation (`date_en_utc`) |

À l'inverse, des titres proches ne sont pas forcément des doublons : « Ecrits antisémites : Jordan Bardella porte plainte pour faux et usage de faux » (Le Monde) et la dépêche EBRA ci-dessus n'ont que 61 % de mots en commun. Ce sont deux articles différents sur le même sujet, qu'on garde tous les deux : c'est le regroupement par thèmes (TD 5) qui les rapprochera.

## Normalisation

Une fonction pure par transformation, dans `src/gazette/normalisation.py`, chacune testée dans `tests/test_normalisation.py`.

| Fonction | Ce qu'elle fait |
|---|---|
| `decoder_entites` | `&eacute;`, `&#039;`, `&nbsp;` deviennent les vrais caractères |
| `retirer_html` | retire les balises (`<p>`, `<b>`...) des titres et extraits |
| `normaliser_espaces` | espaces insécables, tabulations et retours à la ligne deviennent un seul espace |
| `reparer_encodage` | répare l'UTF-8 lu comme du Windows-1252 (`Ã©` devient `é`) |
| `borner_extrait` | coupe l'extrait à 300 caractères, à la fin d'un mot : on ne garde jamais le texte intégral |
| `date_en_utc` | date RFC 822 ou ISO 8601, convertie en UTC (une date sans fuseau est supposée UTC) |
| `titre_pour_comparaison` | minuscules, sans accent ni ponctuation, pour comparer deux titres |
| `similarite_jaccard` | part des mots communs à deux titres, entre 0 et 1 |

## Règles d'exclusion

Les règles sont dans `config/regles.toml` (motifs, rubriques, seuils) et appliquées par `src/gazette/regles.py`. Un article est rejeté par la première règle qui le concerne, dans l'ordre des identifiants ; il va alors dans la table `rejets` avec l'identifiant de la règle. Tests : `tests/test_regles.py`, sur les pollueurs ci-dessus.

| Règle | Ce qu'elle écarte | Pourquoi | Exemple |
|---|---|---|---|
| R01_titre_vide | Titre de moins de 10 caractères, ou gabarit non rempli (`$content`, `{{`) | Rien à afficher dans l'édition | « Vidéo. $content.TitleNoTags » |
| R02_encodage_casse | Titre qui garde des caractères mal encodés après réparation (`Ã`, caractère de remplacement) | Titre illisible dans l'édition | « La rÃ©forme » non réparable |
| R03_sans_date | Item sans date lisible | Impossible de garantir la fraîcheur inférieure à 24 h | Items du Parisien (source écartée pour cette raison) |
| R04_date_future | Date de publication plus de 10 min après la récupération | Date fausse ; 10 min de tolérance pour les horloges des éditeurs | Item daté du lendemain |
| R05_trop_ancien | Publié plus de 24 h avant la récupération | Objectif de fraîcheur de l'édition | « CARTE. Prix des carburants » du 17/09 |
| R06_publi | Publi-reportages, contenus partenaires, promotions (Black Friday, bons plans, codes promo) | Contenu commercial, pas d'actualité | « Black Friday dès le 16 novembre avec des remises jusqu'à 70 % » |
| R07_horoscope | Horoscope, astrologie | Pas d'actualité | « Votre horoscope du jour » |
| R08_service | Programme TV (repéré par le titre), recettes (repérées par l'adresse : `/les-recettes-du-monde/`) | Contenu de service ; le titre seul ne suffit pas, « la recette du succès » est une expression courante | « Le cake au citron et au pavot : la recette de Pascale Weeks » |
| R09_jeux | Loto, EuroMillions, jeux-concours, sudoku, mots fléchés | Pas d'actualité | rubrique « Loto - EuroMillions » |
| R10_doublon | Titre identique (après normalisation) à un article gardé sur les 48 dernières heures | Dépêche reprise à l'identique par plusieurs titres : on garde la première publiée | Dépêches EBRA en double |
| R11_doublon_proche | Titre identique à deux mots près (Jaccard au moins 0,8) | Même dépêche légèrement retouchée | « Bardella a porté plainte » / « Bardella a bien porté plainte » |

Les dates sont comparées à la date de récupération et non à l'heure du nettoyage : rejouer le nettoyage plus tard donne le même résultat.

## Contrôles de qualité

Les contrôles vérifient des faits sur les vraies données, après chaque passage. Ce sont des asset checks Dagster, attachés à l'asset `articles_propres` (`src/gazette/definitions.py`). On a choisi des assertions maison plutôt qu'un outil dédié (Great Expectations, Soda) : quatre requêtes SQL simples suffisent, sans nouvelle dépendance ni configuration à apprendre, et Dagster affiche déjà le résultat et son historique.

| Contrôle | Fait vérifié | Seuil |
|---|---|---|
| `aucune_date_future` | Aucun article gardé n'a une date de publication dans le futur | 0 article, avec 10 min de tolérance |
| `aucun_titre_vide` | Aucun article gardé n'a un titre vide | 0 article |
| `extraits_bornes` | Aucun extrait ne dépasse 300 caractères (pas de texte intégral) | 300 caractères |
| `taux_de_rejet_par_source` | Aucune source n'a plus de 80 % de rejets sur la journée | 80 %, à partir de 10 articles dans la journée |

Quand un contrôle est faux :

- il apparaît en rouge dans Dagster (onglet Checks de l'asset `articles_propres`), avec sa valeur ;
- une alerte part sur le webhook Discord de l'équipe (`DISCORD_WEBHOOK_URL` dans `.env`). Sans webhook, l'alerte reste dans les journaux.

Les chiffres de chaque passage (entrés, gardés, rejetés, rejets par règle, taux de rejet du jour) sont publiés en métadonnées de l'asset `articles_propres` : Dagster en garde l'historique et les trace en courbes (onglet Plots). Le TD 8 les reprendra dans Prometheus.

Pour vérifier le canal d'alerte sans attendre un vrai problème :

```bash
docker compose exec dagster-daemon python -m gazette tester-alerte
```

### Déclencher l'alerte une fois pour de vrai

On rend un fait faux dans les vraies données, on laisse le contrôle le détecter, puis on remet les données en état.

| Date | Passage Dagster | Résultat |
|---|---|---|
| 12/11/2026, 15 h 33 UTC | `2bc18433` | Contrôle `aucune_date_future` en échec, alerte déclenchée mais restée dans les journaux : le webhook n'était pas encore configuré (`alerte non envoyee (DISCORD_WEBHOOK_URL absent)`) |
| 12/11/2026, 16 h 19 UTC | `4040ee1b` | Webhook configuré dans `.env`. Message de test (`tester-alerte`) envoyé, puis contrôle `aucune_date_future` en échec et alerte envoyée et acceptée par Discord : `[gazette] controle de qualite en echec : aucune_date_future (1 article(s) date(s) du futur)`. Les trois autres contrôles sont restés au vert. Article de test supprimé ensuite, collecte planifiée toujours active |

L'adresse du webhook est un secret : elle n'est que dans `.env`, jamais dans le dépôt.

1. Insérer un article daté du lendemain :

   ```bash
   docker compose exec postgres psql -U gazette -d gazette -c "INSERT INTO articles_propres (id, source, lien, titre, resume, publie_le, recupere_le, nettoye_le, passage_id) VALUES ('test-alerte', 'Le Monde', 'https://exemple.invalid/test-alerte', 'Article de test date du futur', '', now() + interval '1 day', now(), now(), 'test-alerte')"
   ```

2. Lancer un passage (ou attendre le suivant) :

   ```bash
   docker compose exec dagster-daemon dagster job launch -j collecte_et_nettoyage -w /opt/dagster/dagster_home/workspace.yaml
   ```

3. Constater le contrôle `aucune_date_future` en rouge dans Dagster et le message sur Discord : `[gazette] controle de qualite en echec : aucune_date_future (1 article(s) date(s) du futur)`.

4. Supprimer l'article de test :

   ```bash
   docker compose exec postgres psql -U gazette -d gazette -c "DELETE FROM articles_propres WHERE id = 'test-alerte'"
   ```

## Rapport de qualité

À chaque passage, le rapport du jour est recalculé depuis les tables et écrit dans `rapports/qualite-AAAA-MM-JJ.md` (un fichier par jour, les jours passés restent archivés). Il donne :

- le nombre d'articles entrés, gardés et rejetés, et le taux de rejet ;
- les rejets par règle ;
- par source : entrés, gardés, rejetés, taux de rejet ;
- les cinq couples (règle, source) qui rejettent le plus, avec un titre en exemple : c'est là qu'on repère une règle trop gourmande.

Pour le regénérer à la main : `docker compose exec dagster-daemon python -m gazette rapport --jour 2026-11-12`.

## Journal des ajustements de règles

| Date | Règle | Changement | Pourquoi |
|---|---|---|---|
| 12/11/2026 | R08_service | Les recettes sont repérées par l'adresse et non plus par « la recette de » dans le titre | Le test sur « Tempête Charles : la recette du succès des secours » montrait un faux positif |
| 12/11/2026 | R08_service | Retrait du motif d'adresse `/programme-tv` | Le premier rapport montrait un faux positif : « Présidentielle : TF1 et LCI organisent un débat » (TV Mag range ses actualités télé sous `/programme-tv/actu-tele/`). L'article a été retraité (voir le runbook) |
| 12/11/2026 | R09_jeux | `loto` et `à gagner` cherchés comme mots entiers | « il va gagner » ne doit pas être pris pour un jeu |
