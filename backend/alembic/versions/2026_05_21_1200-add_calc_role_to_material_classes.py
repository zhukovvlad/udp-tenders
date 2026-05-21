"""add_calc_role_to_material_classes

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-05-21 12:00:00.000000

NOTE: downgrade() on this revision calls drop_column correctly, but the
*previous* revision (a1b2c3d4e5f6) has NotImplementedError in its downgrade().
Running `alembic downgrade -1` will raise before reaching this migration's
drop_column. To roll back only this migration, use its explicit revision:
  alembic downgrade a1b2c3d4e5f6

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Новая колонка: роль класса материала в расчёте avg_price.
    # DEFAULT 'base' — все существующие классы (бетон, арматура) получают роль «основной материал».
    op.add_column(
        "material_classes",
        sa.Column("calc_role", sa.String(), nullable=False, server_default="base"),
    )

    # Индекс для агрегации по счёту в compute_calculations()
    op.create_index(
        "ix_invoice_items_invoice_id_item_type",
        "invoice_items",
        ["invoice_id", "item_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_invoice_items_invoice_id_item_type", table_name="invoice_items")
    op.drop_column("material_classes", "calc_role")
