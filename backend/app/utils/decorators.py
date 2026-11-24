from functools import wraps

from flask import request
from flask_login import current_user

from .responses import ApiError


def admin_required(fn):
    """Server-side admin gate. Unauthenticated -> 401, non-admin -> 403."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            raise ApiError("unauthorized", "Please sign in to continue.", 401)
        if not current_user.is_admin:
            raise ApiError("forbidden", "You do not have access to this resource.", 403)
        return fn(*args, **kwargs)

    return wrapper


def login_required_api(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            raise ApiError("unauthorized", "Please sign in to continue.", 401)
        return fn(*args, **kwargs)

    return wrapper


def get_json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("invalid_json", "Request body must be a JSON object.", 400)
    return data
