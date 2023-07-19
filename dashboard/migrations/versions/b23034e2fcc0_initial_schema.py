"""Initial schema

Revision ID: b23034e2fcc0
Revises: 
Create Date: 2023-07-19 10:26:07.934212

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b23034e2fcc0'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('content_loaded_event',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_uuid_md5', sa.String(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('impression_id', sa.Uuid(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('content_id', sa.Uuid(), nullable=False),
    sa.Column('variant', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('impression_id', 'content_id')
    )
    op.create_table('course',
    sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('term', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('course_activity_stat',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('enrolled_students', sa.Integer(), nullable=False),
    sa.Column('weekly_active_users', sa.Integer(), nullable=False),
    sa.Column('daily_active_users', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('course_id', 'date')
    )
    op.create_table('course_quiz_stat',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('quiz_name', sa.String(), nullable=False),
    sa.Column('graded_quizzes', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('course_id', 'date', 'quiz_name')
    )
    op.create_table('event_user_enrollment',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_uuid_md5', sa.String(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_uuid_md5', 'course_id')
    )
    op.create_table('input_submitted_event',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_uuid_md5', sa.String(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('impression_id', sa.Uuid(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('content_id', sa.Uuid(), nullable=False),
    sa.Column('variant', sa.String(), nullable=False),
    sa.Column('input_content_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('impression_id', 'input_content_id')
    )
    op.create_table('pset_problem_attempted_event',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_uuid_md5', sa.String(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('impression_id', sa.Uuid(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('content_id', sa.Uuid(), nullable=False),
    sa.Column('variant', sa.String(), nullable=False),
    sa.Column('pset_content_id', sa.Uuid(), nullable=False),
    sa.Column('pset_problem_content_id', sa.Uuid(), nullable=False),
    sa.Column('problem_type', sa.String(), nullable=False),
    sa.Column('correct', sa.Boolean(), nullable=False),
    sa.Column('attempt', sa.Integer(), nullable=False),
    sa.Column('final_attempt', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('impression_id', 'pset_problem_content_id', 'attempt')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('pset_problem_attempted_event')
    op.drop_table('input_submitted_event')
    op.drop_table('event_user_enrollment')
    op.drop_table('course_quiz_stat')
    op.drop_table('course_activity_stat')
    op.drop_table('course')
    op.drop_table('content_loaded_event')
    # ### end Alembic commands ###
