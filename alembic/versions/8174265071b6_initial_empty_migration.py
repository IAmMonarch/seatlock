"""initial empty migration

Revision ID: 8174265071b6
Revises:
Create Date: 2026-10-22 00:53:56.821555

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "8174265071b6"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
