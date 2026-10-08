import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from kora_api.access.evaluation import DecisionSource
from kora_api.access.permissions import OverrideEffect, Permission

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class PermissionResponse(BaseModel):
    key: str
    description: str


class RoleDefaultRequest(BaseModel):
    role_key: str
    permission: Permission


class RoleDefaultResponse(BaseModel):
    id: uuid.UUID
    role_key: str
    permission: str
    valid_from: datetime
    valid_to: datetime | None
    created_by_account_id: uuid.UUID | None
    ended_by_account_id: uuid.UUID | None


class OverrideRequest(BaseModel):
    # Overrides have no expiry; unknown fields (e.g. an end date) are rejected.
    model_config = ConfigDict(extra="forbid")

    permission: Permission
    unit_id: uuid.UUID
    effect: OverrideEffect
    reason: Reason


class OverrideResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    permission: str
    unit_id: uuid.UUID
    effect: OverrideEffect
    reason: str
    valid_from: datetime
    valid_to: datetime | None
    created_by_account_id: uuid.UUID
    ended_by_account_id: uuid.UUID | None


class UnitDecisionResponse(BaseModel):
    unit_id: uuid.UUID
    name: str
    kind: str
    allowed: bool
    source: DecisionSource
    decided_at_unit_id: uuid.UUID | None


class PermissionAccessResponse(BaseModel):
    permission: str
    units: list[UnitDecisionResponse]


class EffectiveAccessResponse(BaseModel):
    account_id: uuid.UUID
    at: datetime
    permissions: list[PermissionAccessResponse]


class SystemAdminResponse(BaseModel):
    account_id: uuid.UUID
    username: str
    granted_at: datetime
    granted_by_account_id: uuid.UUID | None
