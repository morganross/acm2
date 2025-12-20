"""Add required configuration fields to presets table.

Revision ID: 003
Revises: 002
Create Date: 2025-12-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add required configuration fields to presets table."""
    
    # Add timing & retry configuration columns with temporary nullable
    op.add_column('presets', sa.Column('max_retries', sa.Integer(), nullable=True))
    op.add_column('presets', sa.Column('retry_delay', sa.Float(), nullable=True))
    op.add_column('presets', sa.Column('request_timeout', sa.Integer(), nullable=True))
    op.add_column('presets', sa.Column('eval_timeout', sa.Integer(), nullable=True))
    
    # Add concurrency configuration columns
    op.add_column('presets', sa.Column('generation_concurrency', sa.Integer(), nullable=True))
    op.add_column('presets', sa.Column('eval_concurrency', sa.Integer(), nullable=True))
    
    # Add iteration configuration columns
    op.add_column('presets', sa.Column('iterations', sa.Integer(), nullable=True))
    op.add_column('presets', sa.Column('eval_iterations', sa.Integer(), nullable=True))
    
    # Add FPF logging configuration columns
    op.add_column('presets', sa.Column('fpf_log_output', sa.String(20), nullable=True))
    op.add_column('presets', sa.Column('fpf_log_file_path', sa.String(500), nullable=True))
    
    # Add post-combine configuration columns
    op.add_column('presets', sa.Column('post_combine_top_n', sa.Integer(), nullable=True))
    
    # Populate existing presets with current hardcoded defaults (migration only)
    op.execute("""
        UPDATE presets 
        SET max_retries = 3,
            retry_delay = 2.0,
            request_timeout = 600,
            eval_timeout = 600,
            generation_concurrency = 5,
            eval_concurrency = 5,
            iterations = 1,
            eval_iterations = 1,
            fpf_log_output = 'file'
        WHERE max_retries IS NULL
    """)
    
    # Make columns NOT NULL after population (except optional ones)
    op.alter_column('presets', 'max_retries', nullable=False)
    op.alter_column('presets', 'retry_delay', nullable=False)
    op.alter_column('presets', 'request_timeout', nullable=False)
    op.alter_column('presets', 'eval_timeout', nullable=False)
    op.alter_column('presets', 'generation_concurrency', nullable=False)
    op.alter_column('presets', 'eval_concurrency', nullable=False)
    op.alter_column('presets', 'iterations', nullable=False)
    op.alter_column('presets', 'eval_iterations', nullable=False)
    op.alter_column('presets', 'fpf_log_output', nullable=False)
    # fpf_log_file_path and post_combine_top_n remain nullable
    
    # Add CHECK constraints for validation
    op.create_check_constraint(
        'check_max_retries',
        'presets',
        'max_retries >= 1 AND max_retries <= 10'
    )
    op.create_check_constraint(
        'check_retry_delay',
        'presets',
        'retry_delay >= 0.5 AND retry_delay <= 30.0'
    )
    op.create_check_constraint(
        'check_request_timeout',
        'presets',
        'request_timeout >= 60 AND request_timeout <= 3600'
    )
    op.create_check_constraint(
        'check_eval_timeout',
        'presets',
        'eval_timeout >= 60 AND eval_timeout <= 3600'
    )
    op.create_check_constraint(
        'check_gen_concurrency',
        'presets',
        'generation_concurrency >= 1 AND generation_concurrency <= 50'
    )
    op.create_check_constraint(
        'check_eval_concurrency',
        'presets',
        'eval_concurrency >= 1 AND eval_concurrency <= 50'
    )
    op.create_check_constraint(
        'check_iterations',
        'presets',
        'iterations >= 1 AND iterations <= 10'
    )
    op.create_check_constraint(
        'check_eval_iterations',
        'presets',
        'eval_iterations >= 1 AND eval_iterations <= 10'
    )
    op.create_check_constraint(
        'check_fpf_log_output',
        'presets',
        "fpf_log_output IN ('stream', 'file', 'none')"
    )
    op.create_check_constraint(
        'check_post_combine_top_n',
        'presets',
        'post_combine_top_n IS NULL OR post_combine_top_n >= 2'
    )


def downgrade() -> None:
    """Remove configuration fields from presets table."""
    
    # Drop CHECK constraints
    op.drop_constraint('check_max_retries', 'presets', type_='check')
    op.drop_constraint('check_retry_delay', 'presets', type_='check')
    op.drop_constraint('check_request_timeout', 'presets', type_='check')
    op.drop_constraint('check_eval_timeout', 'presets', type_='check')
    op.drop_constraint('check_gen_concurrency', 'presets', type_='check')
    op.drop_constraint('check_eval_concurrency', 'presets', type_='check')
    op.drop_constraint('check_iterations', 'presets', type_='check')
    op.drop_constraint('check_eval_iterations', 'presets', type_='check')
    op.drop_constraint('check_fpf_log_output', 'presets', type_='check')
    op.drop_constraint('check_post_combine_top_n', 'presets', type_='check')
    
    # Drop columns
    op.drop_column('presets', 'max_retries')
    op.drop_column('presets', 'retry_delay')
    op.drop_column('presets', 'request_timeout')
    op.drop_column('presets', 'eval_timeout')
    op.drop_column('presets', 'generation_concurrency')
    op.drop_column('presets', 'eval_concurrency')
    op.drop_column('presets', 'iterations')
    op.drop_column('presets', 'eval_iterations')
    op.drop_column('presets', 'fpf_log_output')
    op.drop_column('presets', 'fpf_log_file_path')
    op.drop_column('presets', 'post_combine_top_n')
