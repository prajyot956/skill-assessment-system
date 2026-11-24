"""add admin-managed interview question bank

Revision ID: a18d29c4e6f1
Revises: 5c8d38b4a1f2
Create Date: 2026-11-25

"""
from alembic import op
import sqlalchemy as sa
import re


revision = "a18d29c4e6f1"
down_revision = "5c8d38b4a1f2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("practice_projects", sa.Column("seed_key", sa.String(length=200), nullable=True))
    bind = op.get_bind()
    project_rows = bind.execute(sa.text("SELECT id, title FROM practice_projects")).fetchall()
    for project_id, title in project_rows:
        normalized = title.lower().replace("+", "p").replace("#", "sharp")
        slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or "x"
        bind.execute(
            sa.text("UPDATE practice_projects SET seed_key = :seed_key WHERE id = :id"),
            {"seed_key": f"practice-project:{slug}", "id": project_id},
        )
    op.create_index("uq_practice_projects_seed_key", "practice_projects", ["seed_key"], unique=True)

    op.create_table(
        "interview_question_bank",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seed_key", sa.String(length=64), nullable=True),
        sa.Column("skill_id", sa.Integer(), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_question_bank_skill_id", "interview_question_bank", ["skill_id"], unique=False)
    op.create_index("uq_interview_question_bank_seed_key", "interview_question_bank", ["seed_key"], unique=True)


def downgrade():
    op.drop_index("uq_interview_question_bank_seed_key", table_name="interview_question_bank")
    op.drop_index("ix_interview_question_bank_skill_id", table_name="interview_question_bank")
    op.drop_table("interview_question_bank")
    op.drop_index("uq_practice_projects_seed_key", table_name="practice_projects")
    op.drop_column("practice_projects", "seed_key")
