"""add_alert_ack_evidence_and_pipeline_health

Revision ID: 3463d904417e
Revises: 3afc7378f528
Create Date: 2026-11-15 15:13:34.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3463d904417e'
down_revision: Union[str, None] = '3afc7378f528'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add health_score to pipelines
    op.add_column('pipelines', sa.Column('health_score', sa.Float(), nullable=False, server_default='100.0'))

    # Add acknowledgement and evidence fields to pipeline_alerts
    op.add_column('pipeline_alerts', sa.Column('acknowledged', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('pipeline_alerts', sa.Column('acknowledged_at', sa.DateTime(), nullable=True))
    op.add_column('pipeline_alerts', sa.Column('resolved_at', sa.DateTime(), nullable=True))
    op.add_column('pipeline_alerts', sa.Column('evidence', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('pipeline_alerts', 'evidence')
    op.drop_column('pipeline_alerts', 'resolved_at')
    op.drop_column('pipeline_alerts', 'acknowledged_at')
    op.drop_column('pipeline_alerts', 'acknowledged')
    op.drop_column('pipelines', 'health_score')
