"""update moved learning resource links

Revision ID: 5c8d38b4a1f2
Revises: 879988482778
Create Date: 2026-11-24

"""
from alembic import op
import sqlalchemy as sa


revision = "5c8d38b4a1f2"
down_revision = "879988482778"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    updates = [
        (
            "scikit-learn Tutorials",
            "https://scikit-learn.org/stable/tutorial/index.html",
            "scikit-learn Examples",
            "https://scikit-learn.org/stable/auto_examples/index.html",
        ),
        (
            "Linux Journey",
            "https://linuxjourney.com/",
            "Introduction to Linux (Linux Foundation)",
            "https://training.linuxfoundation.org/training/introduction-to-linux/",
        ),
    ]
    for old_title, old_url, title, url in updates:
        bind.execute(
            sa.text(
                "UPDATE learning_resources SET title = :title, url = :url "
                "WHERE title = :old_title AND url = :old_url"
            ),
            {"title": title, "url": url, "old_title": old_title, "old_url": old_url},
        )


def downgrade():
    bind = op.get_bind()
    updates = [
        (
            "scikit-learn Examples",
            "https://scikit-learn.org/stable/auto_examples/index.html",
            "scikit-learn Tutorials",
            "https://scikit-learn.org/stable/tutorial/index.html",
        ),
        (
            "Introduction to Linux (Linux Foundation)",
            "https://training.linuxfoundation.org/training/introduction-to-linux/",
            "Linux Journey",
            "https://linuxjourney.com/",
        ),
    ]
    for old_title, old_url, title, url in updates:
        bind.execute(
            sa.text(
                "UPDATE learning_resources SET title = :title, url = :url "
                "WHERE title = :old_title AND url = :old_url"
            ),
            {"title": title, "url": url, "old_title": old_title, "old_url": old_url},
        )
