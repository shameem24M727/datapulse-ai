import unittest
from datetime import timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.auth import UserModel, OrganizationModel, UserOrganizationModel
from app.core.security import create_access_token, get_password_hash
from app.core.roles import UserRole
from tests.test_helpers import ensure_test_admin


class TestLoginRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_test_admin()
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Create a dedicated test user with a known test password for login regression
        cls.test_email = "login_regression_user@datapulse.ai"
        cls.test_password = "RegressionTestPassword2026!"
        cls.test_user = cls.db.query(UserModel).filter(UserModel.email == cls.test_email).first()
        if not cls.test_user:
            cls.test_user = UserModel(
                email=cls.test_email,
                hashed_password=get_password_hash(cls.test_password),
                full_name="Regression Test User",
                role=UserRole.ADMIN.value,
                is_active=True,
            )
            cls.db.add(cls.test_user)
            cls.db.commit()
            cls.db.refresh(cls.test_user)

            membership = UserOrganizationModel(
                user_id=cls.test_user.id,
                organization_id="org_default_001",
                role=UserRole.ADMIN.value,
            )
            cls.db.add(membership)
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_successful_login_and_dashboard_access(self):
        """1. Successful login -> /auth/me -> /organizations/ -> /overview/summary."""
        login_res = self.client.post(
            "/api/v1/auth/login",
            json={"email": self.test_email, "password": self.test_password},
        )
        self.assertEqual(login_res.status_code, 200)
        data = login_res.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data.get("token_type"), "bearer")

        headers = {"Authorization": f"Bearer {data['access_token']}"}
        me_res = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["email"], self.test_email)

        orgs_res = self.client.get("/api/v1/organizations/", headers=headers)
        self.assertEqual(orgs_res.status_code, 200)
        self.assertGreaterEqual(len(orgs_res.json()), 1)

        dash_res = self.client.get("/api/v1/overview/summary", headers=headers)
        self.assertEqual(dash_res.status_code, 200)

    def test_02_valid_access_token_and_auth_me(self):
        """2. Valid access token succeeds on /auth/me."""
        token = create_access_token({
            "sub": self.test_user.id,
            "role": self.test_user.role,
            "org_id": "org_default_001",
            "email": self.test_email,
        })
        res = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["id"], self.test_user.id)

    def test_03_missing_or_invalid_token(self):
        """3. Missing or invalid token returns 401."""
        res_missing = self.client.get("/api/v1/auth/me")
        self.assertEqual(res_missing.status_code, 401)

        res_invalid = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        self.assertEqual(res_invalid.status_code, 401)

    def test_04_expired_token(self):
        """4. Expired token returns 401."""
        expired_token = create_access_token(
            {"sub": self.test_user.id, "role": self.test_user.role, "org_id": "org_default_001"},
            expires_delta=timedelta(seconds=-10),
        )
        res = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        self.assertEqual(res.status_code, 401)

    def test_05_failed_profile_request_unknown_user(self):
        """5. Token for non-existent user fails profile request with 401."""
        token = create_access_token({
            "sub": "non_existent_user_id_999",
            "role": UserRole.ADMIN.value,
            "org_id": "org_default_001",
        })
        res = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 401)

    def test_06_existing_admin_account_authentication(self):
        """6. Existing admin account exists, is active, and belongs to default organization."""
        admin = self.db.query(UserModel).filter(UserModel.email == "admin@datapulse.ai").first()
        self.assertIsNotNone(admin)
        self.assertTrue(admin.is_active)

        membership = (
            self.db.query(UserOrganizationModel)
            .filter(
                UserOrganizationModel.user_id == admin.id,
                UserOrganizationModel.organization_id == "org_default_001",
            )
            .first()
        )
        self.assertIsNotNone(membership)

        token = create_access_token({
            "sub": admin.id,
            "role": admin.role,
            "org_id": "org_default_001",
            "email": admin.email,
        })
        me_res = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["email"], "admin@datapulse.ai")

    def test_07_authentication_persistence_across_sessions(self):
        """7. Stored access token remains valid across fresh client requests (simulating page refresh)."""
        login_res = self.client.post(
            "/api/v1/auth/login",
            json={"email": self.test_email, "password": self.test_password},
        )
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["access_token"]

        # Simulate a fresh browser session / page refresh using only the stored token
        fresh_client = TestClient(app)
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(fresh_client.get("/api/v1/auth/me", headers=headers).status_code, 200)
        self.assertEqual(fresh_client.get("/api/v1/organizations/", headers=headers).status_code, 200)

    def test_08_protected_route_behaviour(self):
        """8. Protected dashboard routes reject unauthenticated requests and allow valid tokens."""
        self.assertEqual(self.client.get("/api/v1/overview/summary").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/datasets/").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/organizations/").status_code, 401)

    def test_09_production_sqlite_fallback_disabled(self):
        """9. Production environment refuses silent fallback to ephemeral SQLite if PostgreSQL fails."""
        import os
        from unittest.mock import patch
        from app.db import session as db_session
        from app.core.config import settings

        original_url = settings.DATABASE_URL
        try:
            settings.DATABASE_URL = "postgres://user:pass@127.0.0.1:5999/nonexistent"
            with patch.dict(os.environ, {"RENDER": "true"}):
                with self.assertRaises(RuntimeError) as ctx:
                    db_session.get_engine()
                self.assertIn("SQLite fallback is disabled", str(ctx.exception))
        finally:
            settings.DATABASE_URL = original_url


if __name__ == "__main__":
    unittest.main()
