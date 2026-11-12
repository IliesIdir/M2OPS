"""Crée les tables articles_propres (articles gardés) et rejets (articles écartés et pourquoi).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # L'id est celui de l'item brut (nom du fichier dans articles_bruts/) : on remonte ainsi
    # d'un article propre à son item brut, puis à sa source.
    op.create_table(
        "articles_propres",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("source", sa.Text(), sa.ForeignKey("sources.nom"), nullable=False),
        sa.Column("lien", sa.Text(), nullable=False),
        sa.Column("titre", sa.Text(), nullable=False),
        sa.Column("resume", sa.Text(), nullable=False, server_default=""),
        sa.Column("publie_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recupere_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rubrique", sa.Text(), nullable=True),
        sa.Column("nettoye_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("passage_id", sa.Text(), nullable=False),
        sa.UniqueConstraint("source", "lien", name="article_unique_par_source_et_lien"),
    )
    op.create_index("articles_propres_publie_le", "articles_propres", ["publie_le"])
    op.create_index("articles_propres_nettoye_le", "articles_propres", ["nettoye_le"])

    op.create_table(
        "rejets",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("source", sa.Text(), sa.ForeignKey("sources.nom"), nullable=False),
        sa.Column("lien", sa.Text(), nullable=False),
        sa.Column("titre", sa.Text(), nullable=False),
        sa.Column("regle", sa.Text(), nullable=False),
        sa.Column("publie_le", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recupere_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rejete_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("passage_id", sa.Text(), nullable=False),
    )
    op.create_index("rejets_rejete_le", "rejets", ["rejete_le"])


def downgrade() -> None:
    op.drop_table("rejets")
    op.drop_table("articles_propres")
