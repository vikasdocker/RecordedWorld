"""
Tests for JWT Authentication system.
"""
import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


class TestAuthRegistration:
    def test_register_user(self):
        uid = uuid.uuid4().hex[:8]
        response = client.post("/api/users/register", json={
            "username": f"testuser_auth_{uid}",
            "email": f"test_auth_{uid}@example.com",
            "password": "password123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == f"testuser_auth_{uid}"
        assert data["email"] == f"test_auth_{uid}@example.com"
        assert "id" in data

    def test_register_duplicate_username(self):
        uid = uuid.uuid4().hex[:8]
        uname = f"dup_user_{uid}"
        client.post("/api/users/register", json={
            "username": uname,
            "email": f"dup1_{uid}@example.com",
            "password": "password123"
        })
        response = client.post("/api/users/register", json={
            "username": uname,
            "email": f"dup2_{uid}@example.com",
            "password": "password123"
        })
        assert response.status_code == 400

    def test_register_duplicate_email(self):
        uid = uuid.uuid4().hex[:8]
        email = f"same_{uid}@example.com"
        client.post("/api/users/register", json={
            "username": f"user_a_{uid}",
            "email": email,
            "password": "password123"
        })
        response = client.post("/api/users/register", json={
            "username": f"user_b_{uid}",
            "email": email,
            "password": "password123"
        })
        assert response.status_code == 400


class TestAuthLogin:
    def test_login_success(self):
        uid = uuid.uuid4().hex[:8]
        uname = f"login_user_{uid}"
        client.post("/api/users/register", json={
            "username": uname,
            "email": f"login_{uid}@example.com",
            "password": "password123"
        })
        response = client.post("/api/users/login", json={
            "username": uname,
            "password": "password123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == uname

    def test_login_wrong_password(self):
        uid = uuid.uuid4().hex[:8]
        uname = f"wrong_pass_user_{uid}"
        client.post("/api/users/register", json={
            "username": uname,
            "email": f"wrong_{uid}@example.com",
            "password": "password123"
        })
        response = client.post("/api/users/login", json={
            "username": uname,
            "password": "wrongpassword"
        })
        assert response.status_code == 401

    def test_login_nonexistent_user(self):
        response = client.post("/api/users/login", json={
            "username": f"nonexistent_user_{uuid.uuid4().hex[:8]}",
            "password": "password123"
        })
        assert response.status_code == 401


class TestProtectedEndpoints:
    def get_auth_header(self, username: str = None):
        if username is None:
            username = f"protected_user_{uuid.uuid4().hex[:8]}"
        client.post("/api/users/register", json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "password123"
        })
        login_response = client.post("/api/users/login", json={
            "username": username,
            "password": "password123"
        })
        token = login_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, username

    def test_get_me_authenticated(self):
        headers, username = self.get_auth_header()
        response = client.get("/api/users/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == username

    def test_get_me_unauthenticated(self):
        response = client.get("/api/users/me")
        assert response.status_code == 401

    def test_get_me_invalid_token(self):
        response = client.get("/api/users/me", headers={
            "Authorization": "Bearer invalid_token_here"
        })
        assert response.status_code == 401

    def test_update_profile_authenticated(self):
        headers, username = self.get_auth_header()
        response = client.put(
            "/api/users/me?display_name=New+Name",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "New Name"

    def test_get_user_by_id(self):
        headers, username = self.get_auth_header()
        me_response = client.get("/api/users/me", headers=headers)
        user_id = me_response.json()["id"]

        response = client.get(f"/api/users/{user_id}")
        assert response.status_code == 200
        assert response.json()["username"] == username

    def test_get_nonexistent_user(self):
        response = client.get("/api/users/99999")
        assert response.status_code == 404
