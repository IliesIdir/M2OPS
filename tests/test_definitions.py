"""Vérifie que Dagster se charge, planifie le pipeline et alerte sur un contrôle faux."""

from gazette import definitions
from gazette.definitions import defs, planification_collecte, resultat_du_controle


def test_les_definitions_dagster_se_chargent():
    job = defs.resolve_job_def("collecte_et_nettoyage")

    assert {noeud.name for noeud in job.graph.node_defs} >= {"articles_bruts", "articles_propres"}


def test_les_quatre_controles_de_qualite_sont_declares():
    noms = {cle.name for controle in defs.asset_checks for cle in controle.check_keys}

    assert noms == {
        "aucune_date_future",
        "aucun_titre_vide",
        "extraits_bornes",
        "taux_de_rejet_par_source",
    }


def test_le_pipeline_est_planifie_toutes_les_30_minutes():
    assert planification_collecte.cron_schedule == "*/30 * * * *"
    assert planification_collecte.default_status.value == "RUNNING"


def test_un_controle_faux_declenche_une_alerte(monkeypatch):
    alertes = []
    monkeypatch.setattr(definitions, "envoyer_alerte", alertes.append)

    faux = resultat_du_controle("aucun_titre_vide", {"ok": False, "valeur": 2, "detail": "2 vides"})
    vrai = resultat_du_controle("aucun_titre_vide", {"ok": True, "valeur": 0, "detail": "0 vide"})

    assert not faux.passed and vrai.passed
    assert alertes == ["controle de qualite en echec : aucun_titre_vide (2 vides)"]
