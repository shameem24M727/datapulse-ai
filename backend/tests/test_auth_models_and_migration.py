import unittest
from datetime import datetime, timezone, timedelta
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.auth import UserModel, OrganizationModel, UserOrganizationModel, RefreshTokenModel
from app.models.dataset import DatasetModel
from app.models.pipeline import PipelineModel
from app.core.roles import UserRole, Permission, has_permission, ROLE_PERMISSIONS
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    OrganizationResponse,
    UserResponse,
)

class TestAuthModelsAndMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_01_default_organization_backfill_exists(self):
        # Default org seeded in migration
        default_org = self.db.query(OrganizationModel).filter(OrganizationModel.id == "org_default_001").first()
        self.assertIsNotNone(default_org, "Default organization must exist from migration")
        self.assertEqual(default_org.name, "Default Workspace")
        self.assertEqual(default_org.slug, "default-workspace")
        self.assertTrue(default_org.is_active)

    def test_02_existing_datasets_and_pipelines_have_organization_id(self):
        # Any existing dataset or pipeline must belong to default organization
        datasets = self.db.query(DatasetModel).all()
        for d in datasets:
            self.assertIsNotNone(d.organization_id, f"Dataset {d.id} must be scoped to an organization")

        pipelines = self.db.query(PipelineModel).all()
        for p in pipelines:
            self.assertIsNotNone(p.organization_id, f"Pipeline {p.id} must be scoped to an organization")

    def test_03_user_and_organization_crud_and_relationships(self):
        # 1. Create unique test organization
        test_org = OrganizationModel(
            name="Acme Corp Analytics",
            slug=f"acme-corp-{int(datetime.now(timezone.utc).timestamp())}",
            description="Acme enterprise data quality workspace",
            is_active=True,
        )
        self.db.add(test_org)
        self.db.commit()
        self.db.refresh(test_org)
        self.assertIsNotNone(test_org.id)

        # 2. Create test user
        test_user = UserModel(
            email=f"alice_{int(datetime.now(timezone.utc).timestamp())}@acme.com",
            hashed_password="bcrypt_mock_hash_for_model_test",
            full_name="Alice Engineer",
            role=UserRole.DATA_ENGINEER.value,
            is_active=True,
        )
        self.db.add(test_user)
        self.db.commit()
        self.db.refresh(test_user)
        self.assertIsNotNone(test_user.id)

        # 3. Create membership (UserOrganizationModel)
        membership = UserOrganizationModel(
            user_id=test_user.id,
            organization_id=test_org.id,
            role=UserRole.DATA_ENGINEER.value,
            is_default=True,
        )
        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)

        # Verify relationship from both sides
        self.db.refresh(test_user)
        self.db.refresh(test_org)
        self.assertEqual(len(test_user.memberships), 1)
        self.assertEqual(test_user.memberships[0].organization_id, test_org.id)
        self.assertEqual(len(test_org.members), 1)
        self.assertEqual(test_org.members[0].user_id, test_user.id)

        # 4. Create refresh token
        token = RefreshTokenModel(
            user_id=test_user.id,
            token_hash="sample_sha256_refresh_token_hash",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            is_revoked=False,
        )
        self.db.add(token)
        self.db.commit()
        self.db.refresh(test_user)
        self.assertEqual(len(test_user.refresh_tokens), 1)
        self.assertEqual(test_user.refresh_tokens[0].token_hash, "sample_sha256_refresh_token_hash")

        # Cleanup
        self.db.delete(test_org)
        self.db.delete(test_user)
        self.db.commit()

    def test_04_role_based_permissions_matrix(self):
        # Admin has all permissions
        self.assertTrue(has_permission(UserRole.ADMIN, Permission.USER_MANAGE))
        self.assertTrue(has_permission(UserRole.ADMIN, Permission.DATASET_DELETE))
        self.assertTrue(has_permission(UserRole.ADMIN, Permission.PIPELINE_DELETE))
        self.assertTrue(has_permission(UserRole.ADMIN, Permission.ALERT_RESOLVE))

        # Data Engineer has dataset/pipeline control, but cannot manage users/orgs
        self.assertFalse(has_permission(UserRole.DATA_ENGINEER, Permission.USER_MANAGE))
        self.assertFalse(has_permission(UserRole.DATA_ENGINEER, Permission.ORG_MANAGE))
        self.assertTrue(has_permission(UserRole.DATA_ENGINEER, Permission.DATASET_CREATE))
        self.assertTrue(has_permission(UserRole.DATA_ENGINEER, Permission.DATASET_DELETE))
        self.assertTrue(has_permission(UserRole.DATA_ENGINEER, Permission.PIPELINE_CREATE))
        self.assertTrue(has_permission(UserRole.DATA_ENGINEER, Permission.PIPELINE_MANAGE))
        self.assertTrue(has_permission(UserRole.DATA_ENGINEER, Permission.ALERT_RESOLVE))

        # Analyst can read/create datasets and ack alerts, but cannot delete datasets or pipelines
        self.assertTrue(has_permission(UserRole.ANALYST, Permission.DATASET_READ))
        self.assertTrue(has_permission(UserRole.ANALYST, Permission.DATASET_CREATE))
        self.assertFalse(has_permission(UserRole.ANALYST, Permission.DATASET_DELETE))
        self.assertFalse(has_permission(UserRole.ANALYST, Permission.PIPELINE_DELETE))
        self.assertFalse(has_permission(UserRole.ANALYST, Permission.PIPELINE_MANAGE))
        self.assertTrue(has_permission(UserRole.ANALYST, Permission.ALERT_ACKNOWLEDGE))
        self.assertFalse(has_permission(UserRole.ANALYST, Permission.ALERT_RESOLVE))

        # Viewer has strictly read-only access
        self.assertTrue(has_permission(UserRole.VIEWER, Permission.DATASET_READ))
        self.assertTrue(has_permission(UserRole.VIEWER, Permission.PIPELINE_READ))
        self.assertFalse(has_permission(UserRole.VIEWER, Permission.DATASET_CREATE))
        self.assertFalse(has_permission(UserRole.VIEWER, Permission.DATASET_DELETE))
        self.assertFalse(has_permission(UserRole.VIEWER, Permission.PIPELINE_CREATE))
        self.assertFalse(has_permission(UserRole.VIEWER, Permission.ALERT_ACKNOWLEDGE))
        self.assertFalse(has_permission(UserRole.VIEWER, Permission.ALERT_RESOLVE))

    def test_05_pydantic_auth_schema_validation(self):
        # Valid register request
        req = UserRegisterRequest(
            email="developer@company.com",
            password="StrongPassword123!",
            full_name="Jane Doe",
            role="data_engineer",
            organization_name="Analytics Unit",
        )
        self.assertEqual(req.email, "developer@company.com")
        self.assertEqual(req.role, "data_engineer")

        # Invalid password length (< 8 chars)
        with self.assertRaises(Exception):
            UserRegisterRequest(
                email="dev@company.com",
                password="short",
                full_name="Jane Doe",
            )

        # Invalid email format
        with self.assertRaises(Exception):
            UserRegisterRequest(
                email="not-an-email",
                password="StrongPassword123!",
                full_name="Jane Doe",
            )
