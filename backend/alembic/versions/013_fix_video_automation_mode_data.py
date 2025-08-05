"""Fix video automation mode data - update 'standard' to 'manual'

Revision ID: 013_fix_automation_data
Revises: 012_fix_settings_table_structure
Create Date: 2025-06-23 09:45:00.000000

"""

from typing import Sequence, Union

from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "013_fix_automation_data"
down_revision: Union[str, None] = "012_fix_settings_table_structure"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Fix enum type mismatch where video_automation_mode column is using the wrong enum type.

    The column is currently using video_generation_mode enum (values: 'standard', 'target')
    but should be using video_automation_mode enum (values: 'manual', 'per_capture', 'scheduled', 'milestone').

    This migration:
    1. Creates the correct VideoAutomationMode enum if it doesn't exist
    2. Converts column to text temporarily
    3. Updates the data (convert 'standard' to 'manual')
    4. Converts column to use the correct enum type
    """

    # Create VideoAutomationMode enum if it doesn't exist
    video_automation_mode_enum = postgresql.ENUM(
        "manual",
        "per_capture",
        "scheduled",
        "milestone",
        name="videoautomationmode",
        create_type=False,
    )

    # Try to create the enum type (will be ignored if already exists)
    try:
        video_automation_mode_enum.create(op.get_bind(), checkfirst=True)
    except Exception:
        # Enum might already exist, continue
        pass

    # Step 1: Convert columns to text type temporarily
    op.execute(
        """
        ALTER TABLE cameras 
        ALTER COLUMN video_automation_mode TYPE TEXT
    """
    )

    op.execute(
        """
        ALTER TABLE timelapses 
        ALTER COLUMN video_automation_mode TYPE TEXT
    """
    )

    # Step 2: Update the data while in text format
    op.execute(
        """
        UPDATE cameras 
        SET video_automation_mode = 'manual' 
        WHERE video_automation_mode = 'standard'
    """
    )

    op.execute(
        """
        UPDATE timelapses 
        SET video_automation_mode = 'manual' 
        WHERE video_automation_mode = 'standard'
    """
    )

    # Set any NULL values to 'manual' for cameras
    op.execute(
        """
        UPDATE cameras 
        SET video_automation_mode = 'manual' 
        WHERE video_automation_mode IS NULL
    """
    )

    # Step 3: Convert to the correct enum type
    op.execute(
        """
        ALTER TABLE cameras 
        ALTER COLUMN video_automation_mode 
        TYPE videoautomationmode 
        USING video_automation_mode::videoautomationmode
    """
    )

    op.execute(
        """
        ALTER TABLE timelapses 
        ALTER COLUMN video_automation_mode 
        TYPE videoautomationmode 
        USING video_automation_mode::videoautomationmode
    """
    )


def downgrade() -> None:
    """
    Note: We don't reverse this as 'standard' was never a valid value.
    This migration only fixes data consistency.
    """
    pass
