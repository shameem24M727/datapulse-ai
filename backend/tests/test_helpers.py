import os
import secrets
from app.core.config import settings
from app.core.security import create_access_token
from app.core.roles import UserRole
from app.db.init_db import init_db

def ensure_test_admin():
    from app.models.auth import UserModel
    from app.db.session import SessionLocal
    init_db_needed = True
    db = SessionLocal()
    try:
        admin_user = db.query(UserModel).filter(UserModel.email == "admin@datapulse.ai").first()
        if admin_user:
            init_db_needed = False
    except Exception:
        pass
    finally:
        db.close()

    if init_db_needed:
        if not settings.ADMIN_INITIAL_PASSWORD:
            test_pwd = f"Test_{secrets.token_urlsafe(16)}!Aa1"
            settings.ADMIN_INITIAL_PASSWORD = test_pwd
            try:
                init_db()
            finally:
                settings.ADMIN_INITIAL_PASSWORD = None
        else:
            init_db()

def get_admin_headers(user_id: str = "user_admin_001", org_id: str = "org_default_001") -> dict:
    ensure_test_admin()
    token = create_access_token({
        "sub": user_id,
        "role": UserRole.ADMIN.value,
        "org_id": org_id,
        "email": "admin@datapulse.ai",
    })
    return {"Authorization": f"Bearer {token}"}

def get_admin_token(user_id: str = "user_admin_001", org_id: str = "org_default_001") -> str:
    ensure_test_admin()
    return create_access_token({
        "sub": user_id,
        "role": UserRole.ADMIN.value,
        "org_id": org_id,
        "email": "admin@datapulse.ai",
    })
