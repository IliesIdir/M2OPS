"""Nettoyage : des items bruts vers articles_propres, ou vers rejets avec la règle appliquée."""

import json
import logging
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import Connection, Engine, text

from gazette.normalisation import (
    borner_extrait,
    date_en_utc,
    normaliser_texte,
    titre_pour_comparaison,
)
from gazette.regles import regle_de_rejet

journal = logging.getLogger(__name__)


def ids_deja_traites(moteur: Engine) -> set[str]:
    """Renvoie les identifiants des items déjà gardés ou rejetés lors d'un passage précédent."""
    with moteur.connect() as connexion:
        resultat = connexion.execute(
            text("SELECT id FROM articles_propres UNION SELECT id FROM rejets")
        )
        return set(resultat.scalars())


def lister_nouveaux_bruts(dossier: Path, deja_traites: set[str]) -> list[Path]:
    """Renvoie les fichiers bruts pas encore traités ; le nom du fichier est l'id de l'item."""
    return [chemin for chemin in dossier.glob("*/*.json") if chemin.stem not in deja_traites]


def normaliser_item(brut: dict) -> dict:
    """Transforme un item brut en article : textes nettoyés, extrait borné, dates en UTC."""
    return {
        "id": brut["id"],
        "source": brut["source"],
        "lien": brut["lien"],
        "titre": normaliser_texte(brut["titre"]),
        "resume": borner_extrait(normaliser_texte(brut["resume"])),
        "publie_le": date_en_utc(brut["publie_le"]),
        "recupere_le": date_en_utc(brut["recupere_le"]),
        "rubrique": normaliser_texte(brut["rubrique"]) or None,
    }


def titres_gardes_recents(connexion: Connection, depuis: datetime) -> list[str]:
    """Renvoie les titres gardés depuis une date, au format de comparaison des doublons."""
    resultat = connexion.execute(
        text("SELECT titre FROM articles_propres WHERE publie_le >= :depuis"), {"depuis": depuis}
    )
    return [titre_pour_comparaison(titre) for titre in resultat.scalars()]


def inserer_article(connexion: Connection, article: dict, quand: datetime, passage_id: str) -> None:
    """Ajoute un article gardé dans articles_propres."""
    connexion.execute(
        text(
            """
            INSERT INTO articles_propres (id, source, lien, titre, resume, publie_le,
                                          recupere_le, rubrique, nettoye_le, passage_id)
            VALUES (:id, :source, :lien, :titre, :resume, :publie_le,
                    :recupere_le, :rubrique, :quand, :passage_id)
            """
        ),
        {**article, "quand": quand, "passage_id": passage_id},
    )


def inserer_rejet(
    connexion: Connection, article: dict, regle: str, quand: datetime, passage_id: str
) -> None:
    """Ajoute un article écarté dans rejets, avec l'identifiant de la règle qui l'a écarté."""
    connexion.execute(
        text(
            """
            INSERT INTO rejets (id, source, lien, titre, regle, publie_le,
                                recupere_le, rejete_le, passage_id)
            VALUES (:id, :source, :lien, :titre, :regle, :publie_le,
                    :recupere_le, :quand, :passage_id)
            """
        ),
        {**article, "regle": regle, "quand": quand, "passage_id": passage_id},
    )


def nettoyer(moteur: Engine, dossier: Path, regles: dict, passage_id: str) -> dict:
    """Traite les nouveaux items bruts et renvoie les compteurs du passage."""
    chemins = lister_nouveaux_bruts(dossier, ids_deja_traites(moteur))
    articles = [
        normaliser_item(json.loads(chemin.read_text(encoding="utf-8"))) for chemin in chemins
    ]
    # On traite les articles du plus ancien au plus récent : pour une dépêche reprise par
    # plusieurs titres, c'est la première publiée qui est gardée.
    articles.sort(key=lambda article: article["publie_le"] or article["recupere_le"])

    maintenant = datetime.now(UTC)
    par_regle = Counter()
    par_source = {}
    # Tout le passage est écrit dans une seule transaction : en cas d'erreur, rien n'est
    # enregistré et le passage suivant reprend les mêmes items.
    with moteur.begin() as connexion:
        depuis = maintenant - timedelta(hours=regles["doublons"]["fenetre_heures"])
        titres_gardes = titres_gardes_recents(connexion, depuis)
        for article in articles:
            compteurs = par_source.setdefault(article["source"], Counter())
            compteurs["entres"] += 1
            regle = regle_de_rejet(article, titres_gardes, regles)
            if regle is None:
                inserer_article(connexion, article, maintenant, passage_id)
                titres_gardes.append(titre_pour_comparaison(article["titre"]))
                compteurs["gardes"] += 1
            else:
                inserer_rejet(connexion, article, regle, maintenant, passage_id)
                par_regle[regle] += 1
                compteurs["rejetes"] += 1

    resultat = {
        "entres": len(articles),
        "gardes": sum(c["gardes"] for c in par_source.values()),
        "rejetes": sum(par_regle.values()),
        "par_regle": dict(par_regle),
        "par_source": {source: dict(c) for source, c in par_source.items()},
    }
    journal.info(json.dumps({"evenement": "nettoyage_termine", **resultat}, ensure_ascii=False))
    return resultat
