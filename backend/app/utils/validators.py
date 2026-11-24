import re

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
URL_RE = re.compile(r"^https?://[^\s/$.?#][^\s]*$", re.IGNORECASE)
PHONE_RE = re.compile(r"^[+\d][\d\s\-().]{6,19}$")


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def is_valid_email(value: str) -> bool:
    return bool(value) and len(value) <= 254 and bool(EMAIL_RE.match(value))


def password_errors(password: str) -> list[str]:
    errs = []
    if len(password or "") < 8:
        errs.append("at least 8 characters")
    if len(password or "") > 128:
        errs.append("at most 128 characters")
    if not re.search(r"[a-z]", password or ""):
        errs.append("a lowercase letter")
    if not re.search(r"[A-Z]", password or ""):
        errs.append("an uppercase letter")
    if not re.search(r"\d", password or ""):
        errs.append("a number")
    return errs


def password_message(password: str) -> str | None:
    errs = password_errors(password)
    return ("Password needs " + ", ".join(errs) + ".") if errs else None


def clean_str(value, max_len: int, *, required: bool = False, field: str = "value") -> str | None:
    """Trim a string; returns None for empty optional values."""
    if value is None:
        if required:
            raise ValueError(f"{field} is required.")
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text.")
    value = value.strip()
    if not value:
        if required:
            raise ValueError(f"{field} is required.")
        return None
    if len(value) > max_len:
        raise ValueError(f"{field} must be at most {max_len} characters.")
    return value
