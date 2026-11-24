"""Consistent JSON envelope.

Success: {"success": true,  "data": ..., "meta": {...}?}
Failure: {"success": false, "error": {"code": str, "message": str, "details": {...}?}}
"""
from flask import jsonify


def ok(data=None, status: int = 200, meta: dict | None = None):
    body = {"success": True, "data": data}
    if meta is not None:
        body["meta"] = meta
    return jsonify(body), status


def fail(code: str, message: str, status: int = 400, details: dict | None = None):
    err = {"code": code, "message": message}
    if details:
        err["details"] = details
    return jsonify({"success": False, "error": err}), status


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.status, self.details = code, message, status, details


class ValidationError(ApiError):
    def __init__(self, errors: dict[str, str], message: str = "Please fix the highlighted fields."):
        super().__init__("validation_error", message, 422, {"fields": errors})
