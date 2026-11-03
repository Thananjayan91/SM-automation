"""Tenant/workspace management blueprint."""
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, session, request
)
from flask_login import login_required, current_user

from ..services import tenant_service, permission_service
from ..models.membership import MembershipRole
from .forms import CreateTenantForm, InviteMemberForm, WorkspaceSettingsForm, BrandSettingsForm
from ..web.decorators import tenant_required, require_perm

tenants_bp = Blueprint("tenants", __name__, url_prefix="/workspaces")


@tenants_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    form = CreateTenantForm()
    if form.validate_on_submit():
        tenant, error = tenant_service.create_tenant(
            name=form.name.data,
            owner_user_id=current_user.id,
        )
        if tenant:
            session["active_tenant_id"] = tenant.id
            flash(f"Workspace '{tenant.name}' created!", "success")
            return redirect(url_for("web.dashboard"))
        flash(error, "danger")

    return render_template("tenants/create.html", form=form, title="Create workspace")


@tenants_bp.route("/switch/<tenant_id>")
@login_required
def switch(tenant_id: str):
    """Switch the active workspace."""
    membership = permission_service.get_membership(current_user.id, tenant_id)
    if membership:
        session["active_tenant_id"] = tenant_id
    else:
        flash("Workspace not found.", "warning")
    return redirect(request.referrer or url_for("web.dashboard"))


@tenants_bp.route("/accept-invitation/<token>")
@login_required
def accept_invitation(token: str):
    success, result = tenant_service.accept_invitation(token, current_user.id)
    if success:
        session["active_tenant_id"] = result
        flash("You have joined the workspace!", "success")
        return redirect(url_for("web.dashboard"))
    flash(result, "danger")
    return redirect(url_for("web.dashboard"))
