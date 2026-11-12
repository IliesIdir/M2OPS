"""Rapport de qualité du jour et contrôles de données lancés après chaque passage."""

from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from sqlalchemy import Engine, text

from gazette.normalisation import LONGUEUR_MAX_EXTRAIT


def bornes_du_jour(jour: date) -> dict:
    """Renvoie le début et la fin d'une journée UTC, pour filtrer les tables par date."""
    debut = datetime.combine(jour, time.min, tzinfo=UTC)
    return {"debut": debut, "fin": debut + timedelta(days=1)}


def rapport_du_jour(moteur: Engine, jour: date) -> dict:
    """Compte, pour une journée, les articles entrés, gardés et rejetés, par règle et par source."""
    bornes = bornes_du_jour(jour)
    with moteur.connect() as connexion:
        gardes = connexion.execute(
            text(
                "SELECT source, COUNT(*) FROM articles_propres "
                "WHERE nettoye_le >= :debut AND nettoye_le < :fin GROUP BY source"
            ),
            bornes,
        ).all()
        rejets = connexion.execute(
            text(
                "SELECT source, regle, COUNT(*), MIN(titre) FROM rejets "
                "WHERE rejete_le >= :debut AND rejete_le < :fin GROUP BY source, regle"
            ),
            bornes,
        ).all()

    par_source = {}
    for source, nombre in gardes:
        par_source.setdefault(source, Counter())["gardes"] += nombre
    par_regle = Counter()
    for source, regle, nombre, _ in rejets:
        par_source.setdefault(source, Counter())["rejetes"] += nombre
        par_regle[regle] += nombre
    for compteurs in par_source.values():
        compteurs["entres"] = compteurs["gardes"] + compteurs["rejetes"]

    # Les cinq couples (règle, source) qui rejettent le plus : c'est là qu'on repère une règle
    # trop gourmande. On garde un titre en exemple pour vérifier à l'oeil.
    plus_frequents = sorted(rejets, key=lambda ligne: ligne[2], reverse=True)[:5]
    entres = sum(c["entres"] for c in par_source.values())
    rejetes = sum(par_regle.values())
    return {
        "jour": jour.isoformat(),
        "entres": entres,
        "gardes": entres - rejetes,
        "rejetes": rejetes,
        "taux_rejet": round(rejetes / entres, 3) if entres else 0.0,
        "par_regle": dict(sorted(par_regle.items())),
        "par_source": {source: dict(c) for source, c in sorted(par_source.items())},
        "rejets_frequents": [
            {"regle": regle, "source": source, "nombre": nombre, "exemple": exemple}
            for source, regle, nombre, exemple in plus_frequents
        ],
    }


def rapport_en_markdown(rapport: dict) -> str:
    """Met le rapport en tableaux markdown : par règle, par source, rejets les plus fréquents."""
    lignes = [
        f"# Rapport de qualité du {rapport['jour']}",
        "",
        f"Entrés : {rapport['entres']}, gardés : {rapport['gardes']}, "
        f"rejetés : {rapport['rejetes']} (taux de rejet {rapport['taux_rejet']:.1%}).",
        "",
        "## Rejets par règle",
        "",
        "| Règle | Rejets |",
        "|---|---|",
    ]
    lignes += [f"| {regle} | {nombre} |" for regle, nombre in rapport["par_regle"].items()]
    lignes += [
        "",
        "## Par source",
        "",
        "| Source | Entrés | Gardés | Rejetés | Taux de rejet |",
        "|---|---|---|---|---|",
    ]
    for source, c in rapport["par_source"].items():
        gardes, rejetes = c.get("gardes", 0), c.get("rejetes", 0)
        taux = rejetes / c["entres"] if c["entres"] else 0
        lignes.append(f"| {source} | {c['entres']} | {gardes} | {rejetes} | {taux:.0%} |")
    lignes += [
        "",
        "## Les cinq rejets les plus fréquents",
        "",
        "| Règle | Source | Nombre | Exemple |",
        "|---|---|---|---|",
    ]
    for rejet in rapport["rejets_frequents"]:
        exemple = rejet["exemple"].replace("|", "/")
        lignes.append(f"| {rejet['regle']} | {rejet['source']} | {rejet['nombre']} | {exemple} |")
    return "\n".join(lignes) + "\n"


def ecrire_rapport(rapport: dict, dossier: Path) -> Path:
    """Écrit le rapport du jour dans rapports/qualite-YYYY-MM-DD.md (réécrit à chaque passage)."""
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"qualite-{rapport['jour']}.md"
    chemin.write_text(rapport_en_markdown(rapport), encoding="utf-8")
    return chemin


def controle_dates_futures(moteur: Engine, maintenant: datetime, tolerance_minutes: int) -> dict:
    """Fait vérifié : aucun article gardé n'a une date de publication dans le futur."""
    limite = maintenant + timedelta(minutes=tolerance_minutes)
    with moteur.connect() as connexion:
        nombre = connexion.execute(
            text("SELECT COUNT(*) FROM articles_propres WHERE publie_le > :limite"),
            {"limite": limite},
        ).scalar_one()
    return {"ok": nombre == 0, "valeur": nombre, "detail": f"{nombre} article(s) date(s) du futur"}


def controle_titres_vides(moteur: Engine) -> dict:
    """Fait vérifié : aucun article gardé n'a un titre vide."""
    with moteur.connect() as connexion:
        nombre = connexion.execute(
            text("SELECT COUNT(*) FROM articles_propres WHERE TRIM(titre) = ''")
        ).scalar_one()
    return {"ok": nombre == 0, "valeur": nombre, "detail": f"{nombre} titre(s) vide(s)"}


def controle_extraits_bornes(moteur: Engine) -> dict:
    """Fait vérifié : aucun extrait ne dépasse la longueur maximale (pas de texte intégral)."""
    with moteur.connect() as connexion:
        longueur = connexion.execute(
            text("SELECT COALESCE(MAX(LENGTH(resume)), 0) FROM articles_propres")
        ).scalar_one()
    return {
        "ok": longueur <= LONGUEUR_MAX_EXTRAIT,
        "valeur": longueur,
        "detail": f"extrait le plus long : {longueur} caracteres (maximum {LONGUEUR_MAX_EXTRAIT})",
    }


def controle_taux_rejet(rapport: dict, taux_max: float, entres_min: int) -> dict:
    """Fait vérifié : aucune source ne dépasse le taux de rejet maximal sur la journée."""
    # En dessous d'un minimum d'articles, un taux ne veut rien dire (2 rejets sur 2 = 100 %).
    trop_rejetees = {}
    for source, c in rapport["par_source"].items():
        taux = c.get("rejetes", 0) / c["entres"]
        if c["entres"] >= entres_min and taux > taux_max:
            trop_rejetees[source] = round(taux, 2)
    return {
        "ok": not trop_rejetees,
        "valeur": len(trop_rejetees),
        "detail": f"sources au-dessus de {taux_max:.0%} de rejets : {trop_rejetees or 'aucune'}",
    }
