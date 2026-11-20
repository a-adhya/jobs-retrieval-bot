"""seed allowed emails from JOBBOT_ALLOWED_EMAILS

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-20

The addresses come from the environment so they never get committed. Re-running this later (or
`jobs admin allow-email`) adds new addresses; existing ones are left alone.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jobbot.settings import load_settings

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for email in load_settings().allowed_emails:
        op.get_bind().execute(
            sa.text("INSERT INTO app.allowed_emails (email) VALUES (:email) ON CONFLICT DO NOTHING"),
            {"email": email},
        )


def downgrade() -> None:
    emails = load_settings().allowed_emails
    if emails:
        op.get_bind().execute(
            sa.text("DELETE FROM app.allowed_emails WHERE email = ANY(:emails)"), {"emails": emails}
        )
