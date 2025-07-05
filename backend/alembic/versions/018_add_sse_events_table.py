"""Add SSE events table for database-driven real-time events

Revision ID: 018_add_sse_events_table
Revises: 017_ensure_generation_schedule_columns
Create Date: 2025-01-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "018_add_sse_events_table"
down_revision: Union[str, None] = "017_fix_generation_schedule"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create SSE events table for database-driven real-time event streaming.
    
    This replaces the HTTP POST + in-memory queue pattern with a persistent
    database-driven approach for better reliability and performance.
    """
    
    # Create SSE events table
    op.create_table(
        "sse_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("event_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, 
                 server_default=sa.text("NOW()"), index=True),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True, index=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, default=0),
        sa.Column("priority", sa.String(20), nullable=False, default="normal", index=True),
        sa.Column("source", sa.String(50), nullable=False, default="system"),
        
        # Add indexes for efficient SSE streaming
        sa.Index("idx_sse_events_unprocessed", "created_at", "processed_at", 
                postgresql_where=sa.text("processed_at IS NULL")),
        sa.Index("idx_sse_events_type_created", "event_type", "created_at"),
        sa.Index("idx_sse_events_priority_created", "priority", "created_at"),
    )
    
    # Note: Using VARCHAR instead of enums for flexibility
    # Common event types: image_captured, camera_status_changed, timelapse_status_changed
    # Priority levels: low, normal, high, critical
    
    print("Created sse_events table with indexes for efficient streaming")


def downgrade() -> None:
    """
    Remove SSE events table and related enums.
    """
    
    # Drop table (indexes are dropped automatically)
    op.drop_table("sse_events")
    
    print("Removed sse_events table and related enums")