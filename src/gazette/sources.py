"""Table sources : synchronisation depuis sources.csv et suivi de l'état de collecte."""

import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine, text

# Au-delà de ce nombre d'échecs de suite, la source est mise en sommeil (actif = false).
ECHECS_AVANT_SOMMEIL = 3


def lire_csv(chemin: Path) -> list[dict]:
    """Lit sources.csv et renvoie une ligne par source."""
    with open(chemin, encoding="utf-8", newline="") as fichier:
        return list(csv.DictReader(fichier))


def synchroniser_sources(moteur: Engine, chemin: Path) -> dict:
    """Recopie sources.csv dans la table sources, sans perdre l'état de collecte déjà connu."""
    lignes = lire_csv(chemin)
    noms = [ligne["nom"] for ligne in lignes]
    with moteur.begin() as connexion:
        for ligne in lignes:
            # Une source nouvelle est créée active. Une source connue garde son état (actif,
            # échecs) ; si son adresse change, on oublie l'ETag et le Last-Modified de l'ancienne.
            connexion.execute(
                text(
                    """
                    INSERT INTO sources (nom, type, url_flux)
                    VALUES (:nom, :type, :url_flux)
                    ON CONFLICT (nom) DO UPDATE SET
                        type = excluded.type,
                        etag = CASE WHEN sources.url_flux = excluded.url_flux
                                    THEN sources.etag END,
                        last_modified = CASE WHEN sources.url_flux = excluded.url_flux
                                             THEN sources.last_modified END,
                        url_flux = excluded.url_flux
                    """
                ),
                {"nom": ligne["nom"], "type": ligne["type"], "url_flux": ligne["acces"]},
            )
        # Une source retirée du fichier n'est plus collectée, mais on garde son historique.
        actives = connexion.execute(text("SELECT nom FROM sources WHERE actif")).scalars().all()
        retirees = [nom for nom in actives if nom not in noms]
        for nom in retirees:
            connexion.execute(
                text("UPDATE sources SET actif = false WHERE nom = :nom"), {"nom": nom}
            )
    return {"synchronisees": len(lignes), "desactivees": len(retirees)}


def lister_sources_actives(moteur: Engine) -> list[dict]:
    """Renvoie les sources actives, dans l'ordre alphabétique pour des passages reproductibles."""
    with moteur.connect() as connexion:
        resultat = connexion.execute(
            text(
                "SELECT nom, type, url_flux, etag, last_modified, echecs_consecutifs "
                "FROM sources WHERE actif ORDER BY nom"
            )
        )
        return [dict(ligne._mapping) for ligne in resultat]


def lire_source(moteur: Engine, nom: str) -> dict:
    """Renvoie toutes les colonnes d'une source."""
    with moteur.connect() as connexion:
        ligne = connexion.execute(
            text("SELECT * FROM sources WHERE nom = :nom"), {"nom": nom}
        ).one()
        return dict(ligne._mapping)


def enregistrer_reussite(
    moteur: Engine, nom: str, quand: datetime, etag: str | None, last_modified: str | None
) -> None:
    """Note une collecte réussie : on remet le compteur d'échecs à zéro et on garde les en-têtes."""
    with moteur.begin() as connexion:
        connexion.execute(
            text(
                """
                UPDATE sources
                SET derniere_reussite = :quand, echecs_consecutifs = 0,
                    etag = COALESCE(:etag, etag),
                    last_modified = COALESCE(:last_modified, last_modified)
                WHERE nom = :nom
                """
            ),
            {"nom": nom, "quand": quand, "etag": etag, "last_modified": last_modified},
        )


def enregistrer_echec(moteur: Engine, nom: str) -> bool:
    """Note un échec et met la source en sommeil au 3e de suite ; renvoie True si c'est le cas."""
    with moteur.begin() as connexion:
        echecs = connexion.execute(
            text(
                "UPDATE sources SET echecs_consecutifs = echecs_consecutifs + 1 "
                "WHERE nom = :nom RETURNING echecs_consecutifs"
            ),
            {"nom": nom},
        ).scalar_one()
        if echecs >= ECHECS_AVANT_SOMMEIL:
            connexion.execute(
                text("UPDATE sources SET actif = false WHERE nom = :nom"), {"nom": nom}
            )
            return True
    return False


def reactiver_source(moteur: Engine, nom: str) -> None:
    """Réveille une source mise en sommeil, une fois le problème corrigé."""
    with moteur.begin() as connexion:
        connexion.execute(
            text("UPDATE sources SET actif = true, echecs_consecutifs = 0 WHERE nom = :nom"),
            {"nom": nom},
        )
