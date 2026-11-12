"""Point d'entrée en ligne de commande : python -m gazette <commande>."""

import argparse
import json
import logging
from pathlib import Path

from gazette.base import chemin_sources, creer_moteur, dossier_bruts
from gazette.collecte import collecter_tout
from gazette.premiere_source import lire_premiere_source
from gazette.sources import reactiver_source, synchroniser_sources


def main() -> None:
    """Lit la commande demandée et lance la fonction correspondante."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # Les requêtes HTTP sont déjà résumées dans nos propres lignes de journal.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    parseur = argparse.ArgumentParser(prog="gazette")
    commandes = parseur.add_subparsers(dest="commande", required=True)

    premiere = commandes.add_parser("premiere-source", help="lit une seule source vers un JSON")
    premiere.add_argument("nom", help="nom de la source dans sources.csv, par exemple 'Le Monde'")
    premiere.add_argument("--sources", type=Path, default=Path("sources.csv"))
    premiere.add_argument("--sortie", type=Path, default=Path("articles_bruts"))

    commandes.add_parser("synchroniser-sources", help="recopie sources.csv dans la table sources")
    commandes.add_parser("collecter", help="collecte une fois toutes les sources actives")

    reactiver = commandes.add_parser("reactiver-source", help="réveille une source en sommeil")
    reactiver.add_argument("nom")

    arguments = parseur.parse_args()
    if arguments.commande == "premiere-source":
        lire_premiere_source(arguments.nom, arguments.sources, arguments.sortie)
    elif arguments.commande == "synchroniser-sources":
        print(json.dumps(synchroniser_sources(creer_moteur(), chemin_sources())))
    elif arguments.commande == "collecter":
        print(json.dumps(collecter_tout(creer_moteur(), dossier_bruts())))
    elif arguments.commande == "reactiver-source":
        reactiver_source(creer_moteur(), arguments.nom)


if __name__ == "__main__":
    main()
