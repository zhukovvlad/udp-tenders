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
    # 0. Расширение pg_trgm — нужно для GIN-индекса на name и similarity()
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

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
    op.execute("CREATE INDEX ix_suppliers_name_trgm ON suppliers USING GIN (name gin_trgm_ops)")
    # Частичный уникальный индекс: уникальность имени для поставщиков без ИНН
    op.execute(
        "CREATE UNIQUE INDEX uq_suppliers_name_no_inn ON suppliers (name) WHERE inn IS NULL"
    )

    # 2. Добавляем FK-колонку в invoices + индекс для JOIN/GROUP BY по supplier_id
    op.add_column("invoices", sa.Column("supplier_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_invoices_supplier_id", "invoices", "suppliers", ["supplier_id"], ["id"])
    op.create_index("ix_invoices_supplier_id", "invoices", ["supplier_id"])

    # 3. Миграция данных: создаём записи поставщиков из существующих инвойсов
    #    3a. По ИНН: каноническое имя = самое частое среди инвойсов с этим ИНН
    #    BTRIM нормализует пробельные строки так же, как делает CRUD (.strip() or None).
    op.execute(
        """
        INSERT INTO suppliers (name, inn, created_at)
        WITH counts AS (
            SELECT BTRIM(supplier_inn)  AS supplier_inn,
                   BTRIM(supplier_name) AS supplier_name,
                   COUNT(*) AS cnt
            FROM invoices
            WHERE supplier_inn IS NOT NULL AND BTRIM(supplier_inn) != ''
              AND supplier_name IS NOT NULL AND BTRIM(supplier_name) != ''
            GROUP BY BTRIM(supplier_inn), BTRIM(supplier_name)
        ),
        ranked AS (
            SELECT supplier_inn,
                   supplier_name,
                   ROW_NUMBER() OVER (
                       PARTITION BY supplier_inn
                       ORDER BY cnt DESC, supplier_name
                   ) AS rn
            FROM counts
        )
        SELECT supplier_name, supplier_inn, (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
        FROM ranked
        WHERE rn = 1
        """
    )

    #    3b. Без ИНН: каждый уникальный supplier_name — отдельный поставщик.
    #    Исключаем имена, уже добавленные в шаге 3a (один поставщик мог иметь
    #    инвойсы и с ИНН, и без него).
    op.execute(
        """
        INSERT INTO suppliers (name, inn, created_at)
        SELECT DISTINCT BTRIM(supplier_name), NULL, (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
        FROM invoices
        WHERE (supplier_inn IS NULL OR BTRIM(supplier_inn) = '')
          AND supplier_name IS NOT NULL AND BTRIM(supplier_name) != ''
          AND BTRIM(supplier_name) NOT IN (SELECT name FROM suppliers)
        """
    )

    # 4. Проставляем supplier_id в инвойсах
    #    4a. Инвойсы с ИНН: связываем + канонизируем имя/ИНН из БД
    op.execute(
        """
        UPDATE invoices i
        SET supplier_id    = s.id,
            supplier_name  = s.name,
            supplier_inn   = s.inn
        FROM suppliers s
        WHERE i.supplier_inn IS NOT NULL AND BTRIM(i.supplier_inn) != ''
          AND s.inn = BTRIM(i.supplier_inn)
        """
    )

    #    4b. Инвойсы без ИНН: связываем только с поставщиками, у которых inn IS NULL
    #    (созданными в шаге 3b) — детерминированно.
    #    i.supplier_id IS NULL — не перетираем уже проставленное в шаге 4a.
    op.execute(
        """
        UPDATE invoices i
        SET supplier_id   = s.id,
            supplier_name = s.name,
            supplier_inn  = NULL
        FROM suppliers s
        WHERE (i.supplier_inn IS NULL OR BTRIM(i.supplier_inn) = '')
          AND i.supplier_id IS NULL
          AND s.inn IS NULL
          AND s.name = BTRIM(i.supplier_name)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_invoices_supplier_id", table_name="invoices")
    op.drop_constraint("fk_invoices_supplier_id", "invoices", type_="foreignkey")
    op.drop_column("invoices", "supplier_id")
    op.execute("DROP INDEX IF EXISTS uq_suppliers_name_no_inn")
    op.execute("DROP INDEX IF EXISTS ix_suppliers_name_trgm")
    op.drop_index(op.f("ix_suppliers_id"), table_name="suppliers")
    op.drop_table("suppliers")
    # pg_trgm не удаляем: расширение могло существовать до этой миграции
