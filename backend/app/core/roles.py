from enum import Enum
from typing import Set, Dict

class UserRole(str, Enum):
    ADMIN = "admin"
    DATA_ENGINEER = "data_engineer"
    ANALYST = "analyst"
    VIEWER = "viewer"

class Permission(str, Enum):
    # User & Organization Management
    USER_MANAGE = "user:manage"
    ORG_MANAGE = "org:manage"

    # Datasets
    DATASET_READ = "dataset:read"
    DATASET_CREATE = "dataset:create"
    DATASET_DELETE = "dataset:delete"

    # Pipelines & Streaming
    PIPELINE_READ = "pipeline:read"
    PIPELINE_CREATE = "pipeline:create"
    PIPELINE_DELETE = "pipeline:delete"
    PIPELINE_MANAGE = "pipeline:manage"   # Start/stop, configure simulator

    # Alerts
    ALERT_READ = "alert:read"
    ALERT_ACKNOWLEDGE = "alert:acknowledge"
    ALERT_RESOLVE = "alert:resolve"

    # Copilot & Reports
    COPILOT_QUERY = "copilot:query"
    REPORT_EXPORT = "report:export"

# Role -> Set of Permissions mapping
ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.ADMIN: {
        Permission.USER_MANAGE,
        Permission.ORG_MANAGE,
        Permission.DATASET_READ,
        Permission.DATASET_CREATE,
        Permission.DATASET_DELETE,
        Permission.PIPELINE_READ,
        Permission.PIPELINE_CREATE,
        Permission.PIPELINE_DELETE,
        Permission.PIPELINE_MANAGE,
        Permission.ALERT_READ,
        Permission.ALERT_ACKNOWLEDGE,
        Permission.ALERT_RESOLVE,
        Permission.COPILOT_QUERY,
        Permission.REPORT_EXPORT,
    },
    UserRole.DATA_ENGINEER: {
        Permission.DATASET_READ,
        Permission.DATASET_CREATE,
        Permission.DATASET_DELETE,
        Permission.PIPELINE_READ,
        Permission.PIPELINE_CREATE,
        Permission.PIPELINE_DELETE,
        Permission.PIPELINE_MANAGE,
        Permission.ALERT_READ,
        Permission.ALERT_ACKNOWLEDGE,
        Permission.ALERT_RESOLVE,
        Permission.COPILOT_QUERY,
        Permission.REPORT_EXPORT,
    },
    UserRole.ANALYST: {
        Permission.DATASET_READ,
        Permission.DATASET_CREATE,
        Permission.PIPELINE_READ,
        Permission.ALERT_READ,
        Permission.ALERT_ACKNOWLEDGE,
        Permission.COPILOT_QUERY,
        Permission.REPORT_EXPORT,
    },
    UserRole.VIEWER: {
        Permission.DATASET_READ,
        Permission.PIPELINE_READ,
        Permission.ALERT_READ,
        Permission.REPORT_EXPORT,
    },
}

def has_permission(role: str, permission: Permission) -> bool:
    try:
        user_role = UserRole(role)
        return permission in ROLE_PERMISSIONS.get(user_role, set())
    except ValueError:
        return False
