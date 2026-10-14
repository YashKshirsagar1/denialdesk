from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    clinic_admin = "clinic_admin"
    clinic_staff = "clinic_staff"
    reviewer = "reviewer"
    ops_admin = "ops_admin"


@dataclass
class UserClaims:
    user_id: str
    email: str
    tenant_id: int | None  # None for ops_admin (cross-tenant access)
    role: Role

    @property
    def is_ops(self) -> bool:
        return self.role == Role.ops_admin

    def to_tenant_context(self):
        from denialdesk.repositories.tenant_scoped import TenantContext

        if self.tenant_id is None:
            return None
        return TenantContext(tenant_id=self.tenant_id)
