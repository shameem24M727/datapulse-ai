from app.core.security import create_access_token
from app.core.roles import UserRole
from app.db.init_db import init_db

def get_admin_headers(user_id: str = "user_admin_001", org_id: str = "org_default_001") -> dict:
    init_db()
    token = create_access_token({
        "sub": user_id,
        "role": UserRole.ADMIN.value,
        "org_id": org_id,
        "email": "admin@datapulse.ai",
    })
    return {"Authorization": f"Bearer {token}"}

def get_admin_token(user_id: str = "user_admin_001", org_id: str = "org_default_001") -> str:
    init_db()
    return create_access_token({
        "sub": user_id,
        "role": UserRole.ADMIN.value,
        "org_id": org_id,
        "email": "admin@datapulse.ai",
    })
