from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditLog


async def record_audit(
    session: AsyncSession,
    *,
    user_id: Optional[uuid.UUID],
    action: str,
    target: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    log = AuditLog(user_id=user_id, action=action, target=target, metadata=metadata or {})
    session.add(log)
    await session.flush()
