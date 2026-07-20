"""add hot path indexes

Revision ID: 6e3b8dc47ba9
Revises: d184fbac0a71
Create Date: 2026-07-20 16:55:27.021088

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6e3b8dc47ba9'
down_revision: Union[str, None] = 'd184fbac0a71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создаёт индексы ix_documents_project_id и ix_invoices_document_id_date."""
    # Горячие колонки: project-фильтр и путь documents→invoices(document_id)+date range.
    # На текущих малых данных прироста может не быть (доминируют round-trip'ы) —
    # ставка на масштаб. Прод не развёрнут, таблицы малы → обычная транзакционная
    # миграция допустима; при росте таблиц заменить на CREATE INDEX CONCURRENTLY
    # (autocommit-блок Alembic).
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_index("ix_invoices_document_id_date", "invoices", ["document_id", "date"])


def downgrade() -> None:
    """Удаляет оба индекса в обратном порядке создания."""
    op.drop_index("ix_invoices_document_id_date", table_name="invoices")
    op.drop_index("ix_documents_project_id", table_name="documents")
