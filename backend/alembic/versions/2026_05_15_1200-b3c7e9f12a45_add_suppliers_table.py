"""add_suppliers_table

Revision ID: b3c7e9f12a45
Revises: 11154f78c326
Create Date: 2026-05-15 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c7e9f12a45"
down_revision: Union[str, None] = "11154f78c326"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Создаём таблицу suppliers
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("inn", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inn"),
    )
    op.create_index(op.f("ix_suppliers_id"), "suppliers", ["id"], unique=False)

    # 2. Добавляем FK-колонку в invoices
    op.add_column("invoices", sa.Column("supplier_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_invoices_supplier_id", "invoices", "suppliers", ["supplier_id"], ["id"])

    # 3. Миграция данных: создаём записи поставщиков из существующих инвойсов
    #    3a. По ИНН: каноническое имя = самое частое среди инвойсов с этим ИНН
    op.execute(
        """
        INSERT INTO suppliers (name, inn, created_at)
        SELECT ranked.supplier_name, ranked.supplier_inn, (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
        FROM (
            SELECT supplier_inn,
                   supplier_name,
                   ROW_NUMBER() OVER (
                       PARTITION BY supplier_inn
                       ORDER BY COUNT(*) DESC, supplier_name
                   ) AS rn
            FROM invoices
            WHERE supplier_inn IS NOT NULL AND supplier_inn != ''
              AND supplier_name IS NOT NULL AND supplier_name != ''
            GROUP BY supplier_inn, supplier_name
        ) ranked
        WHERE ranked.rn = 1
        """
    )

    #    3b. Без ИНН: каждый уникальный supplier_name — отдельный поставщик.
    #    Исключаем имена, уже добавленные в шаге 3a (один поставщик мог иметь
    #    инвойсы и с ИНН, и без него).
    op.execute(
        """
        INSERT INTO suppliers (name, inn, created_at)
        SELECT DISTINCT supplier_name, NULL, (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
        FROM invoices
        WHERE (supplier_inn IS NULL OR supplier_inn = '')
          AND supplier_name IS NOT NULL AND supplier_name != ''
          AND supplier_name NOT IN (SELECT name FROM suppliers)
        """
    )

    # 4. Проставляем supplier_id в инвойсах
    #    4a. Инвойсы с ИНН
    op.execute(
        """
        UPDATE invoices i
        SET supplier_id = s.id
        FROM suppliers s
        WHERE i.supplier_inn IS NOT NULL AND i.supplier_inn != ''
          AND s.inn = i.supplier_inn
        """
    )

    #    4b. Инвойсы без ИНН
    op.execute(
        """
        UPDATE invoices i
        SET supplier_id = s.id
        FROM suppliers s
        WHERE (i.supplier_inn IS NULL OR i.supplier_inn = '')
          AND s.inn IS NULL
          AND s.name = i.supplier_name
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_invoices_supplier_id", "invoices", type_="foreignkey")
    op.drop_column("invoices", "supplier_id")
    op.drop_index(op.f("ix_suppliers_id"), table_name="suppliers")
    op.drop_table("suppliers")
