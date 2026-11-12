from flask import Blueprint

api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

from . import auth, tenants, content, jobs, video  # noqa: E402, F401
