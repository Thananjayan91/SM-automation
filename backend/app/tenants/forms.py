"""WTForms for tenant/workspace management."""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, URL


class CreateTenantForm(FlaskForm):
    name = StringField(
        "Workspace name",
        validators=[DataRequired(), Length(min=2, max=255)],
        render_kw={"placeholder": "My Brand", "autofocus": True},
    )
    timezone = SelectField(
        "Timezone",
        choices=[
            ("UTC", "UTC"),
            ("America/New_York", "Eastern Time (US)"),
            ("America/Chicago", "Central Time (US)"),
            ("America/Denver", "Mountain Time (US)"),
            ("America/Los_Angeles", "Pacific Time (US)"),
            ("Europe/London", "London"),
            ("Europe/Paris", "Paris / Berlin"),
            ("Asia/Kolkata", "India (IST)"),
            ("Asia/Singapore", "Singapore"),
            ("Asia/Tokyo", "Tokyo"),
            ("Australia/Sydney", "Sydney"),
        ],
        default="UTC",
    )
    submit = SubmitField("Create workspace")


class InviteMemberForm(FlaskForm):
    email = StringField(
        "Email address",
        validators=[DataRequired(), Length(max=255)],
        render_kw={"placeholder": "colleague@example.com"},
    )
    role = SelectField(
        "Role",
        choices=[
            ("editor", "Editor — create and edit content"),
            ("publisher", "Publisher — review, approve and publish"),
            ("admin", "Admin — manage members and settings"),
        ],
        default="editor",
    )
    submit = SubmitField("Send invitation")


class WorkspaceSettingsForm(FlaskForm):
    name = StringField(
        "Workspace name",
        validators=[DataRequired(), Length(min=2, max=255)],
    )
    timezone = SelectField(
        "Timezone",
        choices=[
            ("UTC", "UTC"),
            ("America/New_York", "Eastern Time (US)"),
            ("America/Chicago", "Central Time (US)"),
            ("America/Denver", "Mountain Time (US)"),
            ("America/Los_Angeles", "Pacific Time (US)"),
            ("Europe/London", "London"),
            ("Europe/Paris", "Paris / Berlin"),
            ("Asia/Kolkata", "India (IST)"),
            ("Asia/Singapore", "Singapore"),
            ("Asia/Tokyo", "Tokyo"),
            ("Australia/Sydney", "Sydney"),
        ],
    )
    submit = SubmitField("Save settings")


class BrandSettingsForm(FlaskForm):
    brand_name = StringField("Brand name", validators=[Optional(), Length(max=255)])
    brand_description = TextAreaField("Brand description", validators=[Optional(), Length(max=2000)])
    brand_voice = TextAreaField(
        "Brand voice / tone instructions",
        validators=[Optional(), Length(max=2000)],
        render_kw={"rows": 4, "placeholder": "Describe the tone and style for AI-generated content..."},
    )
    website_url = StringField("Website URL", validators=[Optional(), URL(), Length(max=2048)])
    submit = SubmitField("Save brand settings")

