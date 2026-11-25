from app.db.base import Base
from app.db.session import engine, SessionLocal
import app.models  # Ensure all models are loaded before create_all
from app.models.auth import OrganizationModel, UserModel, UserOrganizationModel
from app.core.security import get_password_hash
from app.core.roles import UserRole
from app.core.config import settings

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        default_org = db.query(OrganizationModel).filter(OrganizationModel.id == "org_default_001").first()
        if not default_org:
            default_org = OrganizationModel(
                id="org_default_001",
                name="Default Workspace",
                slug="default-workspace",
                description="Default multi-tenant workspace for existing pipelines and datasets",
                is_active=True,
            )
            db.add(default_org)
            db.commit()

        # Seed default admin user if missing
        admin_user = db.query(UserModel).filter(UserModel.email == "admin@datapulse.ai").first()
        if not admin_user:
            if not settings.ADMIN_INITIAL_PASSWORD:
                raise ValueError(
                    "Default admin user does not exist and ADMIN_INITIAL_PASSWORD is not configured. "
                    "Cannot initialize default admin account without a secure password."
                )

            admin_user = UserModel(
                id="user_admin_001",
                email="admin@datapulse.ai",
                hashed_password=get_password_hash(settings.ADMIN_INITIAL_PASSWORD),
                full_name="Platform Administrator",
                role=UserRole.ADMIN.value,
                is_active=True,
            )
            db.add(admin_user)
            db.commit()

            # Ensure membership
            membership = UserOrganizationModel(
                user_id=admin_user.id,
                organization_id="org_default_001",
                role=UserRole.ADMIN.value,
            )
            db.add(membership)
            db.commit()

        # Seed demo users (engineer & viewer) only when explicitly enabled and configured
        if settings.SEED_DEMO_USERS:
            # Seed demo data engineer if missing and configured
            if settings.DEMO_ENGINEER_PASSWORD:
                engineer_user = db.query(UserModel).filter(UserModel.email == "engineer@datapulse.ai").first()
                if not engineer_user:
                    engineer_user = UserModel(
                        id="user_engineer_001",
                        email="engineer@datapulse.ai",
                        hashed_password=get_password_hash(settings.DEMO_ENGINEER_PASSWORD),
                        full_name="Data Reliability Engineer",
                        role=UserRole.DATA_ENGINEER.value,
                        is_active=True,
                    )
                    db.add(engineer_user)
                    db.commit()

                    membership = UserOrganizationModel(
                        user_id=engineer_user.id,
                        organization_id="org_default_001",
                        role=UserRole.DATA_ENGINEER.value,
                    )
                    db.add(membership)
                    db.commit()

            # Seed demo viewer if missing and configured
            if settings.DEMO_VIEWER_PASSWORD:
                viewer_user = db.query(UserModel).filter(UserModel.email == "viewer@datapulse.ai").first()
                if not viewer_user:
                    viewer_user = UserModel(
                        id="user_viewer_001",
                        email="viewer@datapulse.ai",
                        hashed_password=get_password_hash(settings.DEMO_VIEWER_PASSWORD),
                        full_name="Analytics Viewer",
                        role=UserRole.VIEWER.value,
                        is_active=True,
                    )
                    db.add(viewer_user)
                    db.commit()

                    membership = UserOrganizationModel(
                        user_id=viewer_user.id,
                        organization_id="org_default_001",
                        role=UserRole.VIEWER.value,
                    )
                    db.add(membership)
                    db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
