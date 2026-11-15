"""create_pipeline_and_stream_observability_tables

Revision ID: 3afc7378f528
Revises: 06d249dcab6d
Create Date: 2026-11-15 12:50:25.817726

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3afc7378f528'
down_revision: Union[str, None] = '06d249dcab6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. pipelines table
    op.create_table(
        'pipelines',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=255), nullable=False, server_default='HTTP Stream Ingestion'),
        sa.Column('destination', sa.String(length=255), nullable=False, server_default='DataPulse Staging Warehouse'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('schedule', sa.String(length=100), nullable=False, server_default='Real-time Continuous'),
        sa.Column('schema_definition', sa.JSON(), nullable=False),
        sa.Column('total_records_ingested', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_records_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_records_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_rate', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('avg_latency_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('current_throughput_rps', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('last_ingestion_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pipelines_name'), 'pipelines', ['name'], unique=False)
    op.create_index(op.f('ix_pipelines_status'), 'pipelines', ['status'], unique=False)

    # 2. pipeline_metric_snapshots table
    op.create_table(
        'pipeline_metric_snapshots',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('pipeline_id', sa.String(length=36), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('records_in_interval', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('records_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('records_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('throughput_rps', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('avg_latency_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('error_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.ForeignKeyConstraint(['pipeline_id'], ['pipelines.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pipeline_metric_snapshots_pipeline_id'), 'pipeline_metric_snapshots', ['pipeline_id'], unique=False)
    op.create_index(op.f('ix_pipeline_metric_snapshots_timestamp'), 'pipeline_metric_snapshots', ['timestamp'], unique=False)

    # 3. pipeline_alerts table
    op.create_table(
        'pipeline_alerts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('pipeline_id', sa.String(length=36), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('dedup_key', sa.String(length=255), nullable=False),
        sa.Column('occurrence_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('first_occurred_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_occurred_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['pipeline_id'], ['pipelines.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pipeline_alerts_pipeline_id'), 'pipeline_alerts', ['pipeline_id'], unique=False)
    op.create_index(op.f('ix_pipeline_alerts_severity'), 'pipeline_alerts', ['severity'], unique=False)
    op.create_index(op.f('ix_pipeline_alerts_alert_type'), 'pipeline_alerts', ['alert_type'], unique=False)
    op.create_index(op.f('ix_pipeline_alerts_dedup_key'), 'pipeline_alerts', ['dedup_key'], unique=False)

    # 4. pipeline_anomalies table
    op.create_table(
        'pipeline_anomalies',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('pipeline_id', sa.String(length=36), nullable=False),
        sa.Column('column_name', sa.String(length=255), nullable=False),
        sa.Column('anomaly_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=True),
        sa.Column('expected_range', sa.JSON(), nullable=True),
        sa.Column('record_sample', sa.JSON(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['pipeline_id'], ['pipelines.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pipeline_anomalies_pipeline_id'), 'pipeline_anomalies', ['pipeline_id'], unique=False)
    op.create_index(op.f('ix_pipeline_anomalies_detected_at'), 'pipeline_anomalies', ['detected_at'], unique=False)


def downgrade() -> None:
    op.drop_table('pipeline_anomalies')
    op.drop_table('pipeline_alerts')
    op.drop_table('pipeline_metric_snapshots')
    op.drop_table('pipelines')
