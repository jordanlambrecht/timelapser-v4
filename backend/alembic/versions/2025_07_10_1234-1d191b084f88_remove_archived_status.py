"""remove_archived_status

Revision ID: 1d191b084f88
Revises: 242b34aafd0e
Create Date: 2025-07-10 12:34:14.424043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d191b084f88'
down_revision: Union[str, None] = '242b34aafd0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove archived status from timelapses table constraints"""
    # First, convert any existing archived timelapses to completed
    op.execute(
        "UPDATE timelapses SET status = 'completed' WHERE status = 'archived'"
    )
    
    # Drop the old constraint
    op.drop_constraint('timelapses_status_check', 'timelapses', type_='check')
    
    # Add new constraint without archived
    op.create_check_constraint(
        'timelapses_status_check',
        'timelapses',
        "status IN ('running', 'paused', 'completed')"
    )


def downgrade() -> None:
    """Restore archived status to timelapses table constraints"""
    # Drop the new constraint
    op.drop_constraint('timelapses_status_check', 'timelapses', type_='check')
    
    # Add back the old constraint with archived
    op.create_check_constraint(
        'timelapses_status_check',
        'timelapses',
        "status IN ('running', 'paused', 'completed', 'archived')"
    )
