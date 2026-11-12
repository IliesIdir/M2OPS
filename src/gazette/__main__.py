"""Point d'entrée en ligne de commande : python -m gazette <commande>."""

import argparse
import logging
from pathlib import Path

from gazette.premiere_source import lire_premiere_source


def main() -> None:
    """Lit la commande demandée et lance la fonction correspondante."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    parseur = argparse.ArgumentParser(prog="gazette")
    commandes = parseur.add_subparsers(dest="commande", required=True)

    premiere = commandes.add_parser("premiere-source", help="lit une seule source vers un JSON")
    premiere.add_argument("nom", help="nom de la source dans sources.csv, par exemple 'Le Monde'")
    premiere.add_argument("--sources", type=Path, default=Path("sources.csv"))
    premiere.add_argument("--sortie", type=Path, default=Path("articles_bruts"))

    arguments = parseur.parse_args()
    if arguments.commande == "premiere-source":
        lire_premiere_source(arguments.nom, arguments.sources, arguments.sortie)


if __name__ == "__main__":
    main()
