"""Web-layer decorators for tenant context and authorization."""
from functools import wraps

from flask import session, redirect, url_for, flash, abort, g
from flask_login import current_user

from ..extensions import db
from ..services import permission_service
from ..services import tenant_service
from ..models.tenant import Tenant


def tenant_required(f):
    """Ensure the current user has an active tenant in session.

    Loads the tenant and user's membership into flask.g for use
    in the request. Redirects to workspace selection if none set.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        tenant_id = session.get("active_tenant_id")
        if not tenant_id:
            tenants = tenant_service.get_user_tenants(current_user.id)
            if tenants:
                session["active_tenant_id"] = tenants[0].id
                tenant_id = tenants[0].id
            else:
                flash("Please create a workspace to continue.", "info")
                return redirect(url_for("tenants.create"))

        membership = permission_service.get_membership(current_user.id, tenant_id)
        if not membership:
            session.pop("active_tenant_id", None)
            flash("Workspace not found or access denied.", "warning")
            return redirect(url_for("tenants.create"))

        tenant = db.session.get(Tenant, tenant_id)
        if not tenant:
            session.pop("active_tenant_id", None)
            flash("Workspace not found.", "warning")
            return redirect(url_for("tenants.create"))

        g.tenant = tenant
        g.membership = membership

        return f(*args, **kwargs)
    return decorated_function


def require_perm(permission: str):
    """Decorator factory that requires a specific permission.

    Must be used inside a tenant_required-decorated view.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            tenant_id = session.get("active_tenant_id")
            if not tenant_id:
                abort(403)
            if not permission_service.has_permission(current_user.id, tenant_id, permission):
                flash("You do not have permission to perform that action.", "warning")
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator
