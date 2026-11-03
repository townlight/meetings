"""Preserve explicit minutes posting, adoption and signature decisions."""
from alembic import op
import sqlalchemy as sa

revision = "townlight_meetings_0019"
down_revision = "townlight_meetings_0018"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("minutes", sa.Column("decision_history",sa.JSON(),nullable=False,server_default=sa.text("'[]'")),schema="townlight_meetings")


def downgrade():
    raise RuntimeError("Do not discard human decision history; recover forward or restore a consistent backup.")
