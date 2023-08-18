"""Create course_content table

Revision ID: 0f2ac8029e38
Revises: 8748834e91a6
Create Date: 2023-08-14 10:04:48.280245

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0f2ac8029e38'
down_revision = '8748834e91a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('course_content',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('content_id', sa.Uuid(), nullable=False),
    sa.Column('term', sa.String(), nullable=False),
    sa.Column('section', sa.String(), nullable=False),
    sa.Column('activity_name', sa.String(), nullable=False),
    sa.Column('lesson_page', sa.String(), nullable=False),
    sa.Column('visible', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('content_id', 'term')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('course_content')
    # ### end Alembic commands ###