import click
from flask import Flask

from .extensions import db
from .models import User, UserProfile
from .utils.validators import is_valid_email, normalize_email, password_message


def register_cli(app: Flask):
    @app.cli.command("seed")
    def seed():
        """Load skills, assessments, questions, roles, resources and projects (safe to re-run)."""
        from .services.seed_service import seed_all
        click.echo(f"Seeded: {seed_all()}")

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--name", prompt="Full name")
    @click.password_option()
    def create_admin(email, name, password):
        """Create an admin user, or promote an existing account."""
        email = normalize_email(email)
        if not is_valid_email(email):
            raise click.ClickException("Invalid email address.")
        if (msg := password_message(password)):
            raise click.ClickException(msg)
        user = User.query.filter_by(email=email).first()
        if user:
            user.is_admin = True
            click.echo(f"Promoted existing user {email} to admin.")
        else:
            user = User(full_name=name.strip(), email=email, is_admin=True)
            user.set_password(password)
            user.profile = UserProfile()
            db.session.add(user)
            click.echo(f"Created admin {email}.")
        db.session.commit()
