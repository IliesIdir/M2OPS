"""Vérifie que l'orchestration Dagster se charge et planifie bien la collecte."""

from gazette.definitions import defs, planification_collecte


def test_les_definitions_dagster_se_chargent():
    assert defs.resolve_job_def("collecte") is not None


def test_la_collecte_est_planifiee_toutes_les_30_minutes():
    assert planification_collecte.cron_schedule == "*/30 * * * *"
    assert planification_collecte.default_status.value == "RUNNING"
