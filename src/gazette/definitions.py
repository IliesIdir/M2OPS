"""Orchestration Dagster : les assets du pipeline, leur planification et les alertes d'échec."""

from dagster import (
    AssetExecutionContext,
    DefaultScheduleStatus,
    DefaultSensorStatus,
    Definitions,
    MaterializeResult,
    RetryPolicy,
    RunFailureSensorContext,
    ScheduleDefinition,
    asset,
    define_asset_job,
    run_failure_sensor,
)

from gazette.alertes import envoyer_alerte
from gazette.base import creer_moteur, dossier_bruts
from gazette.collecte import collecter_tout


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


job_collecte = define_asset_job("collecte", selection=[articles_bruts])

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
    assets=[articles_bruts],
    jobs=[job_collecte],
    schedules=[planification_collecte],
    sensors=[alerte_echec_passage],
)
