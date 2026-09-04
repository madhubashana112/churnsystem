"""
A tenant repository that keeps no state.

The workspace id *is* the workspace: name and sector are encoded into it, so any
process can resolve a tenant without a shared store. That matters on serverless
hosts, where consecutive requests routinely land on different instances and a
module-level dict would lose the tenant registered a moment earlier.

There is nothing confidential in a workspace — a name and an industry vertical,
both supplied by whoever is looking at the page — so the id is encoded rather
than signed. The sector is re-validated on decode so a hand-made id can never
select an unknown sector core.
"""
import base64
import binascii
import json
import uuid
from typing import Optional

from churn_platform.domain.interfaces.i_repository import ITenantRepository
from churn_platform.domain.models.tenant import Tenant

VALID_SECTORS = ("SaaS", "Telecom", "FinTech")
MAX_NAME_LENGTH = 120


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def encode_tenant_id(name: str, sector: str) -> str:
    """Build a self-describing workspace id."""
    payload = {
        "n": str(name)[:MAX_NAME_LENGTH],
        "s": sector,
        # Keeps ids unique for repeat registrations of the same name and sector.
        "u": uuid.uuid4().hex[:8],
    }
    return _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def decode_tenant_id(tenant_id: str) -> Optional[Tenant]:
    """The tenant an id describes, or None if it is malformed or unrecognised."""
    if not tenant_id:
        return None
    try:
        payload = json.loads(_b64decode(tenant_id).decode("utf-8"))
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    name = payload.get("n")
    sector = payload.get("s")

    # A crafted id must never reach get_sector_core with an unknown sector.
    if sector not in VALID_SECTORS:
        return None
    if not isinstance(name, str) or not name.strip():
        return None

    return Tenant(tenant_id=tenant_id, name=name[:MAX_NAME_LENGTH], sector=sector)


class StatelessTenantRepository(ITenantRepository):
    async def save(self, tenant: Tenant) -> None:
        """No-op: the id already carries everything needed to rebuild the tenant."""
        return None

    async def get(self, tenant_id: str) -> Optional[Tenant]:
        return decode_tenant_id(tenant_id)
