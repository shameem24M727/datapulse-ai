from app.db.base import Base
from app.db.session import engine, SessionLocal
import app.models  # Ensure all models are loaded before create_all
from app.models.auth import OrganizationModel, UserModel, UserOrganizationModel
from app.core.security import get_password_hash
from app.core.roles import UserRole

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
            admin_user = UserModel(
                id="user_admin_001",
                email="admin@datapulse.ai",
                hashed_password=get_password_hash("AdminSecure2026!"),
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
    except Exception:
        db.rollback()
    finally:
        db.close()
