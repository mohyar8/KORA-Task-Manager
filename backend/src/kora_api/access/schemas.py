import uuid

from pydantic import BaseModel, Field

from kora_api.access.policy import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH


class SignInRequest(BaseModel):
    # Loose bounds only: format problems must produce the generic credential failure, not a 422.
    username: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=1024)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class AccountResponse(BaseModel):
    id: uuid.UUID
    username: str
    must_change_password: bool
    is_system_admin: bool


class SessionResponse(BaseModel):
    account: AccountResponse
    csrf_token: str
