"""Authentication blueprint — login, register, logout, password reset."""
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, session, current_app
)
from flask_login import login_user, logout_user, login_required, current_user
from ..extensions import limiter
from ..services import auth_service
from ..services import tenant_service
from .forms import LoginForm, RegisterForm, ForgotPasswordForm, ResetPasswordForm
from ..models.user import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = auth_service.authenticate_user(form.email.data, form.password.data)
        if user:
            login_user(user, remember=form.remember_me.data)
            auth_service.create_web_session(user)

            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)

            tenants = tenant_service.get_user_tenants(user.id)
            if tenants:
                session["active_tenant_id"] = tenants[0].id
                return redirect(url_for("web.dashboard"))
            return redirect(url_for("tenants.create"))
        else:
            flash("Invalid email or password.", "danger")

    return render_template("auth/login.html", form=form, title="Sign in")


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        user, error = auth_service.register_user(
            email=form.email.data,
            password=form.password.data,
            name=form.name.data,
        )
        if user:
            login_user(user)
            auth_service.create_web_session(user)
            flash("Account created! Set up your first workspace.", "success")
            return redirect(url_for("tenants.create"))
        else:
            flash(error, "danger")

    return render_template("auth/register.html", form=form, title="Create account")


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    auth_service.logout_user_session(current_user)
    logout_user()
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))

    form = ForgotPasswordForm()
    sent = False
    if form.validate_on_submit():
        auth_service.generate_password_reset_token(form.email.data)
        sent = True

    return render_template("auth/forgot_password.html", form=form, sent=sent, title="Reset password")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def reset_password(token: str):
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        success, error = auth_service.consume_password_reset_token(token, form.password.data)
        if success:
            flash("Password reset successfully. Please sign in.", "success")
            return redirect(url_for("auth.login"))
        else:
            flash(error, "danger")

    return render_template("auth/reset_password.html", form=form, token=token, title="Set new password")
