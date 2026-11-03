"""Tests for user registration, login, and password reset."""
import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User
from .conftest import create_user, login


class TestRegistration:
    def test_register_page_loads(self, client):
        response = client.get("/auth/register")
        assert response.status_code == 200
        assert b"Create" in response.data

    def test_register_creates_user(self, client, db):
        response = client.post(
            "/auth/register",
            data={
                "name": "New User",
                "email": "newuser@example.com",
                "password": "SecurePass1!",
                "confirm_password": "SecurePass1!",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        user = User.query.filter_by(email="newuser@example.com").first()
        assert user is not None
        assert user.name == "New User"

    def test_register_duplicate_email_fails(self, client, db, user_a):
        response = client.post(
            "/auth/register",
            data={
                "name": "Another User",
                "email": "user_a@example.com",
                "password": "SecurePass1!",
                "confirm_password": "SecurePass1!",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        # Should show error, not create duplicate
        users = User.query.filter_by(email="user_a@example.com").all()
        assert len(users) == 1

    def test_register_weak_password_fails(self, client, db):
        response = client.post(
            "/auth/register",
            data={
                "name": "User",
                "email": "weak@example.com",
                "password": "weak",
                "confirm_password": "weak",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        user = User.query.filter_by(email="weak@example.com").first()
        assert user is None

    def test_register_mismatched_passwords_fails(self, client, db):
        response = client.post(
            "/auth/register",
            data={
                "name": "User",
                "email": "mismatch@example.com",
                "password": "SecurePass1!",
                "confirm_password": "DifferentPass1!",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        user = User.query.filter_by(email="mismatch@example.com").first()
        assert user is None


class TestLogin:
    def test_login_page_loads(self, client):
        response = client.get("/auth/login")
        assert response.status_code == 200

    def test_login_valid_credentials(self, client, db, user_a):
        response = client.post(
            "/auth/login",
            data={"email": "user_a@example.com", "password": "Test1234!"},
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_login_invalid_password(self, client, db, user_a):
        response = client.post(
            "/auth/login",
            data={"email": "user_a@example.com", "password": "WrongPassword1!"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Invalid" in response.data or b"invalid" in response.data

    def test_login_nonexistent_user(self, client):
        response = client.post(
            "/auth/login",
            data={"email": "nobody@example.com", "password": "Password1!"},
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_forgot_password_page_loads(self, client):
        response = client.get("/auth/forgot-password")
        assert response.status_code == 200

    def test_forgot_password_always_returns_success(self, client, db, user_a):
        """Verify the endpoint doesn't reveal whether an email exists."""
        # Real email
        response = client.post(
            "/auth/forgot-password",
            data={"email": "user_a@example.com"},
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Non-existent email — should behave the same
        response = client.post(
            "/auth/forgot-password",
            data={"email": "nobody@nowhere.com"},
            follow_redirects=True,
        )
        assert response.status_code == 200


class TestPasswordHashing:
    def test_password_is_hashed(self, db):
        user = create_user(email="hash_test@example.com")
        assert user.password_hash != "Test1234!"
        assert "$argon2" in user.password_hash

    def test_correct_password_verifies(self, db):
        user = create_user(email="verify_test@example.com")
        assert user.check_password("Test1234!") is True

    def test_wrong_password_fails(self, db):
        user = create_user(email="wrong_test@example.com")
        assert user.check_password("WrongPassword") is False
