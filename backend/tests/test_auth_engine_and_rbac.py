import unittest
import time
from datetime import datetime, timezone, timedelta
from jose import jwt, ExpiredSignatureError, JWTError
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.auth import UserModel, OrganizationModel, UserOrganizationModel, RefreshTokenModel
from app.core.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    decode_access_token,
    create_refresh_token,
    hash_token,
)
from app.core.config import settings
from app.core.roles import UserRole, Permission, has_permission
from app.services.auth_service import auth_service
from app.api.deps import (
    get_current_user,
    get_current_active_user,
    get_current_organization,
    require_roles,
    require_permission,
)

# Test mini-app to test FastAPI dependencies in isolation
test_auth_app = FastAPI()

@test_auth_app.get("/test/protected")
def protected_route(user: UserModel = Depends(get_current_active_user)):
    return {"user_id": user.id, "email": user.email}

@test_auth_app.get("/test/organization")
def org_route(org: OrganizationModel = Depends(get_current_organization)):
    return {"org_id": org.id, "slug": org.slug}

@test_auth_app.get("/test/admin-only")
def admin_only_route(user: UserModel = Depends(require_roles([UserRole.ADMIN.value]))):
    return {"message": "Admin access granted", "user": user.email}

@test_auth_app.get("/test/data-engineer-only")
def engineer_only_route(
    user: UserModel = Depends(require_roles([UserRole.ADMIN.value, UserRole.DATA_ENGINEER.value]))
):
    return {"message": "Engineer access granted", "user": user.email}

@test_auth_app.get("/test/permission-dataset-delete")
def permission_route(user: UserModel = Depends(require_permission(Permission.DATASET_DELETE))):
    return {"message": "Permission granted", "user": user.email}

class TestAuthEngineAndRBAC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(test_auth_app)

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_01_password_hashing_and_verification(self):
        raw_pw = "SuperSecureP@ssw0rd2026!"
        hashed = hash_password(raw_pw)

        # Hash must not match plaintext
        self.assertNotEqual(raw_pw, hashed)
        self.assertTrue(hashed.startswith("$2b$") or hashed.startswith("$2a$"))

        # Verification
        self.assertTrue(verify_password(raw_pw, hashed))
        self.assertFalse(verify_password("WrongPassword123!", hashed))
        self.assertFalse(verify_password("", hashed))

    def test_02_password_complexity_validation(self):
        # Valid passwords
        self.assertTrue(validate_password_strength("ValidPass123")[0])
        self.assertTrue(validate_password_strength("Complex_Pass_2026!")[0])

        # Too short (< 8 chars)
        ok, msg = validate_password_strength("Short1!")
        self.assertFalse(ok)
        self.assertIn("at least 8 characters", msg)

        # No numbers
        ok, msg = validate_password_strength("NoNumbersAtAll!")
        self.assertFalse(ok)
        self.assertIn("at least one number", msg)

        # No letters
        ok, msg = validate_password_strength("1234567890123")
        self.assertFalse(ok)
        self.assertIn("at least one letter", msg)

    def test_03_jwt_creation_and_decoding(self):
        payload = {
            "sub": "user_abc_123",
            "email": "user@datapulse.ai",
            "role": "analyst",
            "org_id": "org_default_001",
        }
        token = create_access_token(payload, expires_delta=timedelta(minutes=15))
        self.assertIsInstance(token, str)

        decoded = decode_access_token(token)
        self.assertEqual(decoded["sub"], "user_abc_123")
        self.assertEqual(decoded["email"], "user@datapulse.ai")
        self.assertEqual(decoded["role"], "analyst")
        self.assertEqual(decoded["org_id"], "org_default_001")
        self.assertIn("exp", decoded)
        self.assertIn("iat", decoded)

    def test_04_jwt_expired_token_rejection(self):
        payload = {"sub": "user_expired", "email": "exp@datapulse.ai"}
        # Issue token that already expired 10 seconds ago
        expired_token = create_access_token(payload, expires_delta=timedelta(seconds=-10))

        with self.assertRaises(ExpiredSignatureError):
            decode_access_token(expired_token)

    def test_05_jwt_invalid_signature_rejection(self):
        payload = {"sub": "user_forged", "email": "fake@datapulse.ai"}
        # Sign with wrong secret
        tampered_token = jwt.encode(payload, "wrong_secret_signature", algorithm="HS256")

        with self.assertRaises(JWTError):
            decode_access_token(tampered_token)

    def test_06_refresh_token_rotation_and_revocation(self):
        timestamp = int(datetime.now(timezone.utc).timestamp())
        # 1. Register a user
        user, org, access_token, raw_refresh = auth_service.register_user(
            db=self.db,
            email=f"rot_{timestamp}@test.com",
            password="Password123!",
            full_name="Rotation Test",
            role=UserRole.ANALYST.value,
        )
        self.assertIsNotNone(access_token)
        self.assertIsNotNone(raw_refresh)

        # 2. Check refresh token is stored hashed in DB
        hashed_token = hash_token(raw_refresh)
        db_token = self.db.query(RefreshTokenModel).filter(RefreshTokenModel.token_hash == hashed_token).first()
        self.assertIsNotNone(db_token)
        self.assertFalse(db_token.is_revoked)

        # 3. Rotate refresh token -> receives new pair and old is revoked
        u, o, new_access, new_raw_refresh = auth_service.rotate_refresh_token(self.db, raw_refresh)
        self.assertNotEqual(access_token, new_access)
        self.assertNotEqual(raw_refresh, new_raw_refresh)

        # Verify old token record is revoked in DB
        self.db.refresh(db_token)
        self.assertTrue(db_token.is_revoked)

        # 4. Attempting to reuse revoked token must be rejected with 401
        with self.assertRaises(HTTPException) as ctx:
            auth_service.rotate_refresh_token(self.db, raw_refresh)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("revoked", ctx.exception.detail.lower())

        # 5. Revoke new refresh token on logout
        success = auth_service.revoke_refresh_token(self.db, new_raw_refresh)
        self.assertTrue(success)

        # Cleanup
        self.db.delete(user)
        self.db.delete(org)
        self.db.commit()

    def test_07_fastapi_dependency_missing_credentials(self):
        # No header
        res = self.client.get("/test/protected")
        self.assertEqual(res.status_code, 401)
        self.assertIn("Authentication credentials were not provided", res.json()["detail"])

        # Malformed bearer
        res2 = self.client.get("/test/protected", headers={"Authorization": "Bearer not_a_valid_token"})
        self.assertEqual(res2.status_code, 401)

    def test_08_fastapi_dependency_active_user_and_organization(self):
        timestamp = int(datetime.now(timezone.utc).timestamp())
        user, org, access_token, _ = auth_service.register_user(
            db=self.db,
            email=f"dep_{timestamp}@test.com",
            password="Password123!",
            full_name="Dependency Test",
            role=UserRole.DATA_ENGINEER.value,
        )

        headers = {"Authorization": f"Bearer {access_token}"}

        # 1. Access protected route
        res = self.client.get("/test/protected", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["user_id"], user.id)

        # 2. Access organization route
        res_org = self.client.get("/test/organization", headers=headers)
        self.assertEqual(res_org.status_code, 200)
        self.assertEqual(res_org.json()["org_id"], org.id)

        # 3. Disable user -> must return 403 Forbidden
        user.is_active = False
        self.db.commit()

        res_disabled = self.client.get("/test/protected", headers=headers)
        self.assertEqual(res_disabled.status_code, 403)
        self.assertIn("disabled", res_disabled.json()["detail"])

        # Cleanup
        self.db.delete(user)
        self.db.delete(org)
        self.db.commit()

    def test_09_rbac_role_and_permission_dependencies(self):
        timestamp = int(datetime.now(timezone.utc).timestamp())
        # Create a Viewer user
        viewer_user, viewer_org, viewer_token, _ = auth_service.register_user(
            db=self.db,
            email=f"viewer_{timestamp}@test.com",
            password="Password123!",
            full_name="Viewer User",
            role=UserRole.VIEWER.value,
        )
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        # Create an Admin user
        admin_user, admin_org, admin_token, _ = auth_service.register_user(
            db=self.db,
            email=f"admin_{timestamp}@test.com",
            password="Password123!",
            full_name="Admin User",
            role=UserRole.ADMIN.value,
        )
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Create a Data Engineer user
        eng_user, eng_org, eng_token, _ = auth_service.register_user(
            db=self.db,
            email=f"eng_{timestamp}@test.com",
            password="Password123!",
            full_name="Engineer User",
            role=UserRole.DATA_ENGINEER.value,
        )
        eng_headers = {"Authorization": f"Bearer {eng_token}"}

        # 1. Admin accessing admin-only endpoint -> 200 OK
        res = self.client.get("/test/admin-only", headers=admin_headers)
        self.assertEqual(res.status_code, 200)

        # 2. Viewer accessing admin-only endpoint -> 403 Forbidden
        res_viewer = self.client.get("/test/admin-only", headers=viewer_headers)
        self.assertEqual(res_viewer.status_code, 403)
        self.assertIn("Forbidden", res_viewer.json()["detail"])

        # 3. Engineer accessing engineer-only endpoint -> 200 OK
        res_eng = self.client.get("/test/data-engineer-only", headers=eng_headers)
        self.assertEqual(res_eng.status_code, 200)

        # 4. Viewer accessing engineer-only endpoint -> 403 Forbidden
        res_viewer_eng = self.client.get("/test/data-engineer-only", headers=viewer_headers)
        self.assertEqual(res_viewer_eng.status_code, 403)

        # 5. Permission: Dataset Delete (Admin & Engineer have it; Viewer does not)
        self.assertEqual(self.client.get("/test/permission-dataset-delete", headers=admin_headers).status_code, 200)
        self.assertEqual(self.client.get("/test/permission-dataset-delete", headers=eng_headers).status_code, 200)
        self.assertEqual(self.client.get("/test/permission-dataset-delete", headers=viewer_headers).status_code, 403)

        # Cleanup
        self.db.delete(viewer_user)
        self.db.delete(viewer_org)
        self.db.delete(admin_user)
        self.db.delete(admin_org)
        self.db.delete(eng_user)
        self.db.delete(eng_org)
        self.db.commit()
