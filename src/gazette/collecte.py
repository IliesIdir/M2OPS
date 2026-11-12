"""Collecteur multi-sources : une source après l'autre, poliment, avec reprise sur erreur."""

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import feedparser
import httpx
from sqlalchemy import Engine

from gazette.alertes import envoyer_alerte
from gazette.flux import creer_client, parser_flux
from gazette.sources import (
    ECHECS_AVANT_SOMMEIL,
    enregistrer_echec,
    enregistrer_reussite,
    lister_sources_actives,
)
from gazette.stockage_brut import ecrire_item

journal = logging.getLogger(__name__)

TENTATIVES = 3
ATTENTE_INITIALE_SECONDES = 2


class ErreurTransitoire(Exception):
    """Erreur qui vaut la peine d'être réessayée : code 5xx, timeout, connexion coupée."""


def telecharger_avec_reprise(
    client: httpx.Client,
    url: str,
    etag: str | None,
    last_modified: str | None,
    attente_initiale: float = ATTENTE_INITIALE_SECONDES,
) -> httpx.Response:
    """Télécharge un flux avec les en-têtes conditionnels et réessaie les erreurs transitoires."""
    # On renvoie l'ETag et le Last-Modified reçus la dernière fois : si le flux n'a pas changé,
    # l'éditeur répond 304 sans renvoyer le contenu.
    entetes = {}
    if etag:
        entetes["If-None-Match"] = etag
    if last_modified:
        entetes["If-Modified-Since"] = last_modified

    for tentative in range(1, TENTATIVES + 1):
        try:
            reponse = client.get(url, headers=entetes)
            # Un 304 veut dire "rien de nouveau" : c'est une réussite, pas une erreur.
            if reponse.status_code == 304:
                return reponse
            if reponse.status_code < 500:
                # Un 4xx n'est pas réessayé : redemander tout de suite donnerait la même réponse.
                reponse.raise_for_status()
                return reponse
            erreur = ErreurTransitoire(f"code HTTP {reponse.status_code}")
        except (httpx.TimeoutException, httpx.TransportError) as exception:
            erreur = ErreurTransitoire(f"{type(exception).__name__}")
        if tentative < TENTATIVES:
            # Attente croissante (2 s, puis 4 s) pour ne pas insister sur un serveur en difficulté.
            attente = attente_initiale * 2 ** (tentative - 1)
            journal.info("tentative %d/%d echouee pour %s (%s)", tentative, TENTATIVES, url, erreur)
            time.sleep(attente)
    raise erreur


def collecter_source(
    moteur: Engine,
    client: httpx.Client,
    source: dict,
    dossier: Path,
    attente_initiale: float = ATTENTE_INITIALE_SECONDES,
) -> dict:
    """Collecte une source, écrit ses nouveaux items et met à jour son état en base."""
    debut = time.monotonic()
    ligne = {"evenement": "collecte_source", "source": source["nom"], "recus": 0, "ecrits": 0}
    try:
        reponse = telecharger_avec_reprise(
            client, source["url_flux"], source["etag"], source["last_modified"], attente_initiale
        )
        recupere_le = datetime.now(UTC)
        if reponse.status_code == 304:
            ligne["statut"] = "non_modifie"
        else:
            items = parser_flux(reponse.content, source["nom"])
            # Un contenu non vide dont on ne tire aucun item est un flux cassé, pas un flux vide.
            if not items and feedparser.parse(reponse.content).bozo:
                raise ValueError("flux illisible")
            ligne["statut"] = "ok"
            ligne["recus"] = len(items)
            for item in items:
                if ecrire_item(dossier, item, recupere_le.isoformat()):
                    ligne["ecrits"] += 1
        enregistrer_reussite(
            moteur,
            source["nom"],
            recupere_le,
            reponse.headers.get("ETag"),
            reponse.headers.get("Last-Modified"),
        )
    except (ErreurTransitoire, httpx.HTTPError, ValueError) as erreur:
        ligne["statut"] = "echec"
        ligne["erreur"] = str(erreur)
        if enregistrer_echec(moteur, source["nom"]):
            ligne["mise_en_sommeil"] = True
            message = (
                f"source mise en sommeil apres {ECHECS_AVANT_SOMMEIL} echecs consecutifs : "
                f"{source['nom']} ({erreur})"
            )
            journal.warning(json.dumps({"evenement": "source_mise_en_sommeil", "message": message}))
            envoyer_alerte(message)

    ligne["ignores"] = ligne["recus"] - ligne["ecrits"]
    ligne["duree_s"] = round(time.monotonic() - debut, 2)
    # Une ligne de journal en JSON par source : facile à lire et à filtrer plus tard.
    journal.info(json.dumps(ligne, ensure_ascii=False))
    return ligne


def collecter_tout(
    moteur: Engine, dossier: Path, attente_initiale: float = ATTENTE_INITIALE_SECONDES
) -> dict:
    """Collecte les sources actives une par une et renvoie les compteurs du passage."""
    sources = lister_sources_actives(moteur)
    totaux = {"sources": len(sources), "ok": 0, "non_modifie": 0, "echec": 0, "en_sommeil": 0}
    totaux.update({"recus": 0, "ecrits": 0, "ignores": 0})
    # Les sources sont traitées en séquence : jamais deux requêtes en même temps chez un éditeur.
    with creer_client() as client:
        for source in sources:
            ligne = collecter_source(moteur, client, source, dossier, attente_initiale)
            totaux[ligne["statut"]] += 1
            totaux["en_sommeil"] += 1 if ligne.get("mise_en_sommeil") else 0
            for compteur in ("recus", "ecrits", "ignores"):
                totaux[compteur] += ligne[compteur]
    journal.info(json.dumps({"evenement": "collecte_terminee", **totaux}))
    return totaux
