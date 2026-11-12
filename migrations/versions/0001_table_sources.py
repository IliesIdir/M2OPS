"""Crée la table sources, qui garde l'état de collecte de chaque flux.

Revision ID: 0001
Revises:
Create Date: 2026-11-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("nom", sa.Text(), primary_key=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("url_flux", sa.Text(), nullable=False),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("derniere_reussite", sa.DateTime(timezone=True), nullable=True),
        sa.Column("echecs_consecutifs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("last_modified", sa.Text(), nullable=True),
        sa.CheckConstraint("type IN ('PQR', 'PQN')", name="type_pqr_ou_pqn"),
    )


def downgrade() -> None:
    op.drop_table("sources")
