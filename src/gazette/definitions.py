"""Orchestration Dagster : assets du pipeline, contrôles, planification et alertes."""

from datetime import UTC, datetime

from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetExecutionContext,
    DefaultScheduleStatus,
    DefaultSensorStatus,
    Definitions,
    MaterializeResult,
    MetadataValue,
    RetryPolicy,
    RunFailureSensorContext,
    ScheduleDefinition,
    asset,
    asset_check,
    define_asset_job,
    run_failure_sensor,
)

from gazette.alertes import envoyer_alerte
from gazette.base import chemin_regles, creer_moteur, dossier_bruts, dossier_rapports
from gazette.collecte import collecter_tout
from gazette.nettoyage import nettoyer
from gazette.qualite import (
    controle_dates_futures,
    controle_extraits_bornes,
    controle_taux_rejet,
    controle_titres_vides,
    ecrire_rapport,
    rapport_du_jour,
)
from gazette.regles import charger_regles


# On réessaie tout le passage deux fois, une minute plus tard, si une erreur imprévue
# l'interrompt (base indisponible au redémarrage par exemple). Les erreurs d'une source
# sont déjà gérées dans le collecteur et n'arrêtent pas le passage.
@asset(
    group_name="collecte",
    retry_policy=RetryPolicy(max_retries=2, delay=60),
    description="Items bruts de toutes les sources actives, un fichier JSON par item.",
)
def articles_bruts(context: AssetExecutionContext) -> MaterializeResult:
    totaux = collecter_tout(creer_moteur(), dossier_bruts())
    context.log.info(f"collecte terminee : {totaux}")
    # Les compteurs du passage sont publiés en métadonnées : Dagster en garde l'historique.
    return MaterializeResult(metadata=totaux)


@asset(
    deps=[articles_bruts],
    group_name="nettoyage",
    retry_policy=RetryPolicy(max_retries=2, delay=60),
    description="Articles normalisés et gardés ; les écartés vont dans la table rejets.",
)
def articles_propres(context: AssetExecutionContext) -> MaterializeResult:
    moteur = creer_moteur()
    # L'identifiant du passage Dagster est gardé sur chaque ligne : on retrouve ainsi
    # le passage, et ses journaux, qui a écrit un article.
    resultat = nettoyer(moteur, dossier_bruts(), charger_regles(chemin_regles()), context.run_id)
    rapport = rapport_du_jour(moteur, datetime.now(UTC).date())
    chemin = ecrire_rapport(rapport, dossier_rapports())
    context.log.info(
        f"nettoyage termine : {resultat['gardes']} gardes, {resultat['rejetes']} rejetes"
    )
    return MaterializeResult(
        metadata={
            "entres": resultat["entres"],
            "gardes": resultat["gardes"],
            "rejetes": resultat["rejetes"],
            "rejets_par_regle": MetadataValue.json(resultat["par_regle"]),
            "taux_rejet_du_jour": rapport["taux_rejet"],
            "rapport_du_jour": MetadataValue.path(str(chemin)),
        }
    )


def resultat_du_controle(nom: str, controle: dict) -> AssetCheckResult:
    """Transforme un contrôle en résultat Dagster et prévient l'équipe s'il est faux."""
    if not controle["ok"]:
        envoyer_alerte(f"controle de qualite en echec : {nom} ({controle['detail']})")
    return AssetCheckResult(
        passed=controle["ok"],
        severity=AssetCheckSeverity.ERROR,
        metadata={"valeur": controle["valeur"], "detail": controle["detail"]},
    )


@asset_check(asset=articles_propres, description="Aucun article gardé n'est daté du futur.")
def aucune_date_future() -> AssetCheckResult:
    tolerance = charger_regles(chemin_regles())["fraicheur"]["tolerance_futur_minutes"]
    controle = controle_dates_futures(creer_moteur(), datetime.now(UTC), tolerance)
    return resultat_du_controle("aucune_date_future", controle)


@asset_check(asset=articles_propres, description="Aucun article gardé n'a un titre vide.")
def aucun_titre_vide() -> AssetCheckResult:
    return resultat_du_controle("aucun_titre_vide", controle_titres_vides(creer_moteur()))


@asset_check(asset=articles_propres, description="Aucun extrait ne dépasse 300 caractères.")
def extraits_bornes() -> AssetCheckResult:
    return resultat_du_controle("extraits_bornes", controle_extraits_bornes(creer_moteur()))


@asset_check(asset=articles_propres, description="Aucune source ne dépasse 80 % de rejets du jour.")
def taux_de_rejet_par_source() -> AssetCheckResult:
    seuils = charger_regles(chemin_regles())["controles"]
    rapport = rapport_du_jour(creer_moteur(), datetime.now(UTC).date())
    controle = controle_taux_rejet(rapport, seuils["taux_rejet_max"], seuils["entres_min"])
    return resultat_du_controle("taux_de_rejet_par_source", controle)


# Un passage = collecte puis nettoyage, suivis des contrôles de qualité.
job_collecte = define_asset_job(
    "collecte_et_nettoyage", selection=[articles_bruts, articles_propres]
)

# Toutes les 30 minutes, la fréquence maximale fixée dans le cadrage pour être poli.
planification_collecte = ScheduleDefinition(
    job=job_collecte,
    cron_schedule="*/30 * * * *",
    execution_timezone="Europe/Paris",
    default_status=DefaultScheduleStatus.RUNNING,
)


@run_failure_sensor(default_status=DefaultSensorStatus.RUNNING)
def alerte_echec_passage(context: RunFailureSensorContext) -> None:
    """Prévient l'équipe quand un passage du pipeline échoue malgré les reprises."""
    envoyer_alerte(
        f"passage en echec : {context.dagster_run.job_name} ({context.failure_event.message})"
    )


defs = Definitions(
    assets=[articles_bruts, articles_propres],
    asset_checks=[aucune_date_future, aucun_titre_vide, extraits_bornes, taux_de_rejet_par_source],
    jobs=[job_collecte],
    schedules=[planification_collecte],
    sensors=[alerte_echec_passage],
)
