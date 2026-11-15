import time
import json
import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.auth import UserModel, OrganizationModel, UserOrganizationModel
from app.models.pipeline import PipelineModel
from app.core.security import create_access_token, get_password_hash
from app.core.roles import UserRole
from app.api.v1.endpoints.auth import FAILED_ATTEMPTS

class TestAuthAndMultiTenancy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Seed two distinct test organizations for multi-tenancy verification
        cls.org_a = cls.db.query(OrganizationModel).filter(OrganizationModel.slug == "alpha-corp").first()
        if not cls.org_a:
            cls.org_a = OrganizationModel(
                name="Alpha Corp",
                slug="alpha-corp",
                description="Alpha tenant",
                is_active=True,
            )
            cls.db.add(cls.org_a)
            cls.db.commit()

        cls.org_b = cls.db.query(OrganizationModel).filter(OrganizationModel.slug == "beta-corp").first()
        if not cls.org_b:
            cls.org_b = OrganizationModel(
                name="Beta Corp",
                slug="beta-corp",
                description="Beta tenant",
                is_active=True,
            )
            cls.db.add(cls.org_b)
            cls.db.commit()

        # Seed User in Org A (Engineer)
        cls.user_alpha = cls.db.query(UserModel).filter(UserModel.email == "alpha_engineer@alphacorp.com").first()
        if not cls.user_alpha:
            cls.user_alpha = UserModel(
                email="alpha_engineer@alphacorp.com",
                hashed_password=get_password_hash("AlphaSecurePass2026!"),
                full_name="Alpha Engineer",
                role=UserRole.DATA_ENGINEER.value,
                is_active=True,
            )
            cls.db.add(cls.user_alpha)
            cls.db.commit()
            cls.db.add(UserOrganizationModel(user_id=cls.user_alpha.id, organization_id=cls.org_a.id, role=UserRole.DATA_ENGINEER.value))
            cls.db.commit()

        # Seed User in Org B (Engineer)
        cls.user_beta = cls.db.query(UserModel).filter(UserModel.email == "beta_engineer@betacorp.com").first()
        if not cls.user_beta:
            cls.user_beta = UserModel(
                email="beta_engineer@betacorp.com",
                hashed_password=get_password_hash("BetaSecurePass2026!"),
                full_name="Beta Engineer",
                role=UserRole.DATA_ENGINEER.value,
                is_active=True,
            )
            cls.db.add(cls.user_beta)
            cls.db.commit()
            cls.db.add(UserOrganizationModel(user_id=cls.user_beta.id, organization_id=cls.org_b.id, role=UserRole.DATA_ENGINEER.value))
            cls.db.commit()

        # Seed Viewer User in Org A
        cls.user_viewer = cls.db.query(UserModel).filter(UserModel.email == "alpha_viewer@alphacorp.com").first()
        if not cls.user_viewer:
            cls.user_viewer = UserModel(
                email="alpha_viewer@alphacorp.com",
                hashed_password=get_password_hash("ViewerPass2026!"),
                full_name="Alpha Viewer",
                role=UserRole.VIEWER.value,
                is_active=True,
            )
            cls.db.add(cls.user_viewer)
            cls.db.commit()
            cls.db.add(UserOrganizationModel(user_id=cls.user_viewer.id, organization_id=cls.org_a.id, role=UserRole.VIEWER.value))
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        FAILED_ATTEMPTS.clear()

    # ── 1. Registration & Login ──────────────────────────────────────────────

    def test_01_user_registration_success(self):
        unique_email = f"user_{int(time.time() * 1000)}@datapulse.ai"
        res = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email,
                "password": "StrongPassword2026!",
                "full_name": "New Team Lead",
                "organization_name": "New Analytics Org",
                "role": "data_engineer",
            },
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.assertGreater(data["expires_in"], 0)
        self.assertIn("dp_refresh_token", res.cookies)

    def test_02_registration_validation_rules(self):
        # 1. Weak password (no special char or digit)
        res_weak = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak_pwd@test.com",
                "password": "weakpassword",
                "organization_name": "Org",
            },
        )
        self.assertEqual(res_weak.status_code, 422)

        # 2. Duplicate email
        res_dup = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": self.user_alpha.email,
                "password": "ValidPassword2026!",
                "full_name": "Alpha Duplicate",
                "organization_name": "Alpha Org",
            },
        )
        self.assertEqual(res_dup.status_code, 409)
        self.assertIn("already exists", res_dup.json()["detail"])

    def test_03_login_and_rate_limiting_lockout(self):
        # Valid login
        res_valid = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": self.user_alpha.email,
                "password": "AlphaSecurePass2026!",
            },
        )
        self.assertEqual(res_valid.status_code, 200)
        data = res_valid.json()
        self.assertIn("access_token", data)

        # 5 consecutive failed logins trigger 429 lockout
        for i in range(5):
            res_fail = self.client.post(
                "/api/v1/auth/login",
                json={
                    "email": self.user_alpha.email,
                    "password": "WrongPassword!",
                },
            )
            self.assertEqual(res_fail.status_code, 401)

        # 6th attempt triggers 429
        res_lockout = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": self.user_alpha.email,
                "password": "AlphaSecurePass2026!",
            },
        )
        self.assertEqual(res_lockout.status_code, 429)
        self.assertIn("Too many failed login attempts", res_lockout.json()["detail"])

    def test_04_refresh_token_lifecycle_and_rotation(self):
        # 1. Login to obtain refresh token
        res_login = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": self.user_alpha.email,
                "password": "AlphaSecurePass2026!",
            },
        )
        self.assertEqual(res_login.status_code, 200)
        old_rt = res_login.json()["refresh_token"]

        # 2. Refresh session
        res_refresh = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_rt},
        )
        self.assertEqual(res_refresh.status_code, 200)
        new_data = res_refresh.json()
        new_rt = new_data["refresh_token"]
        self.assertNotEqual(old_rt, new_rt)

        # 3. Attempting to reuse old_rt triggers revocation / reuse alert
        res_reuse = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_rt},
        )
        self.assertEqual(res_reuse.status_code, 401)

    def test_05_current_user_and_logout(self):
        token_alpha = create_access_token(
            subject=self.user_alpha.id,
            role=self.user_alpha.role,
            organization_id=self.org_a.id,
        )

        # 1. Get profile
        res_me = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token_alpha}"},
        )
        self.assertEqual(res_me.status_code, 200)
        me_data = res_me.json()
        self.assertEqual(me_data["email"], self.user_alpha.email)
        self.assertEqual(me_data["role"], "data_engineer")

        # 2. Request without token returns 401
        res_no_auth = self.client.get("/api/v1/auth/me")
        self.assertEqual(res_no_auth.status_code, 401)

    # ── 2. Organizations & Multi-Tenancy ─────────────────────────────────────

    def test_06_organization_management_and_tenant_switching(self):
        token_alpha = create_access_token(
            subject=self.user_alpha.id,
            role=self.user_alpha.role,
            organization_id=self.org_a.id,
        )

        # 1. List organizations
        res_orgs = self.client.get(
            "/api/v1/organizations/",
            headers={"Authorization": f"Bearer {token_alpha}"},
        )
        self.assertEqual(res_orgs.status_code, 200)
        orgs = res_orgs.json()
        self.assertTrue(any(o["id"] == self.org_a.id for o in orgs))

        # 2. Create organization
        new_org_name = f"Project Gamma {int(time.time() * 1000)}"
        res_create = self.client.post(
            "/api/v1/organizations/",
            json={"name": new_org_name, "description": "Gamma isolation project"},
            headers={"Authorization": f"Bearer {token_alpha}"},
        )
        self.assertEqual(res_create.status_code, 201)
        created_org = res_create.json()
        self.assertEqual(created_org["name"], new_org_name)

        # 3. Switch active organization
        res_switch = self.client.post(
            f"/api/v1/organizations/switch/{created_org['id']}",
            headers={"Authorization": f"Bearer {token_alpha}"},
        )
        self.assertEqual(res_switch.status_code, 200)
        switch_tokens = res_switch.json()
        self.assertIn("access_token", switch_tokens)

    # ── 3. RBAC Permissions ──────────────────────────────────────────────────

    def test_07_rbac_role_restrictions(self):
        token_viewer = create_access_token(
            subject=self.user_viewer.id,
            role=UserRole.VIEWER.value,
            organization_id=self.org_a.id,
        )

        # Viewer can list pipelines (read-only)
        res_list = self.client.get(
            "/api/v1/pipelines/",
            headers={"Authorization": f"Bearer {token_viewer}"},
        )
        self.assertEqual(res_list.status_code, 200)

        # Viewer CANNOT create pipelines (403 Forbidden)
        res_create = self.client.post(
            "/api/v1/pipelines/",
            json={
                "name": "Viewer Illegal Stream",
                "source": "Kafka",
                "destination": "S3",
                "schema_definition": {
                    "fields": [{"name": "id", "type": "string", "required": True}],
                    "strict": False,
                },
            },
            headers={"Authorization": f"Bearer {token_viewer}"},
        )
        self.assertEqual(res_create.status_code, 403)
        self.assertIn("Missing permission", res_create.json()["detail"])

        # Viewer CANNOT upload datasets (403 Forbidden)
        res_upload = self.client.post(
            "/api/v1/datasets/upload",
            files={"file": ("test.csv", b"id,val\n1,10\n", "text/csv")},
            headers={"Authorization": f"Bearer {token_viewer}"},
        )
        self.assertEqual(res_upload.status_code, 403)

    # ── 4. Cross-Tenant IDOR Protection ──────────────────────────────────────

    def test_08_cross_tenant_isolation_and_idor_protection(self):
        token_alpha = create_access_token(
            subject=self.user_alpha.id,
            role=self.user_alpha.role,
            organization_id=self.org_a.id,
        )
        token_beta = create_access_token(
            subject=self.user_beta.id,
            role=self.user_beta.role,
            organization_id=self.org_b.id,
        )

        # 1. User Alpha creates pipeline in Org A
        res_pipe = self.client.post(
            "/api/v1/pipelines/",
            json={
                "name": "Alpha Sensitive Financial Stream",
                "source": "Alpha Bank API",
                "destination": "Alpha Warehouse",
                "schema_definition": {
                    "fields": [{"name": "txn_id", "type": "string", "required": True}],
                    "strict": False,
                },
            },
            headers={"Authorization": f"Bearer {token_alpha}"},
        )
        self.assertEqual(res_pipe.status_code, 201)
        alpha_pipe_id = res_pipe.json()["id"]

        # 2. User Alpha can access pipeline
        res_own = self.client.get(
            f"/api/v1/pipelines/{alpha_pipe_id}",
            headers={"Authorization": f"Bearer {token_alpha}"},
        )
        self.assertEqual(res_own.status_code, 200)

        # 3. User Beta (from Org B) tries to read Alpha's pipeline -> 404 (IDOR protected, no leakage)
        res_cross_read = self.client.get(
            f"/api/v1/pipelines/{alpha_pipe_id}",
            headers={"Authorization": f"Bearer {token_beta}"},
        )
        self.assertEqual(res_cross_read.status_code, 404)

        # 4. User Beta tries to ingest into Alpha's pipeline -> 404
        res_cross_ingest = self.client.post(
            f"/api/v1/pipelines/{alpha_pipe_id}/ingest",
            json={"record": {"key": "malicious"}},
            headers={"Authorization": f"Bearer {token_beta}"},
        )
        self.assertEqual(res_cross_ingest.status_code, 404)

        # 5. User Beta tries to stop Alpha's pipeline -> 404
        res_cross_stop = self.client.post(
            f"/api/v1/pipelines/{alpha_pipe_id}/stop",
            headers={"Authorization": f"Bearer {token_beta}"},
        )
        self.assertEqual(res_cross_stop.status_code, 404)

        # 6. User Beta tries to delete Alpha's pipeline -> 404
        res_cross_delete = self.client.delete(
            f"/api/v1/pipelines/{alpha_pipe_id}",
            headers={"Authorization": f"Bearer {token_beta}"},
        )
        self.assertEqual(res_cross_delete.status_code, 404)

        # Cleanup: Alpha can delete their own pipeline
        res_cleanup = self.client.delete(
            f"/api/v1/pipelines/{alpha_pipe_id}",
            headers={"Authorization": f"Bearer {token_alpha}"},
        )
        self.assertEqual(res_cleanup.status_code, 200)

    # ── 5. WebSocket Authentication & Cross-Tenant Rejection ─────────────────

    def test_09_websocket_authentication_and_tenant_security(self):
        token_alpha = create_access_token(
            subject=self.user_alpha.id,
            role=self.user_alpha.role,
            organization_id=self.org_a.id,
        )
        token_beta = create_access_token(
            subject=self.user_beta.id,
            role=self.user_beta.role,
            organization_id=self.org_b.id,
        )

        # Create pipeline in Org A
        res_pipe = self.client.post(
            "/api/v1/pipelines/",
            json={
                "name": "Alpha Live WebSocket Pipeline",
                "source": "MQTT",
                "destination": "DB",
                "schema_definition": {
                    "fields": [{"name": "reading_id", "type": "string", "required": True}],
                    "strict": False,
                },
            },
            headers={"Authorization": f"Bearer {token_alpha}"},
        )
        self.assertEqual(res_pipe.status_code, 201)
        pipe_id = res_pipe.json()["id"]

        try:
            # 1. Connecting without token rejected
            with self.assertRaises(Exception):
                with self.client.websocket_connect(f"/api/v1/pipelines/{pipe_id}/ws") as ws:
                    ws.receive_text()

            # 2. Connecting with forged token rejected
            with self.assertRaises(Exception):
                with self.client.websocket_connect(f"/api/v1/pipelines/{pipe_id}/ws?token=forged.invalid.token") as ws:
                    ws.receive_text()

            # 3. Connecting across tenants (Beta token for Alpha's pipeline) rejected with 4003
            with self.assertRaises(Exception):
                with self.client.websocket_connect(f"/api/v1/pipelines/{pipe_id}/ws?token={token_beta}") as ws:
                    ws.receive_text()

            # 4. Connecting with valid Org A token succeeds and receives initial state packet
            with self.client.websocket_connect(f"/api/v1/pipelines/{pipe_id}/ws?token={token_alpha}") as ws:
                raw_pkt = ws.receive_text()
                pkt = json.loads(raw_pkt)
                self.assertEqual(pkt["type"], "initial_state")
                self.assertEqual(pkt["pipeline_id"], pipe_id)
                self.assertEqual(pkt["pipeline"]["name"], "Alpha Live WebSocket Pipeline")
        finally:
            self.client.delete(f"/api/v1/pipelines/{pipe_id}", headers={"Authorization": f"Bearer {token_alpha}"})

if __name__ == "__main__":
    unittest.main()
