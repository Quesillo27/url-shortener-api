from datetime import datetime, timezone
from typing import Optional
import string

from pydantic import BaseModel, field_validator


def validate_alias(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    allowed = string.ascii_letters + string.digits + "-_"
    if not all(char in allowed for char in value):
        raise ValueError("El alias solo puede contener letras, numeros, guiones y guiones bajos")
    if len(value) < 3 or len(value) > 50:
        raise ValueError("El alias debe tener entre 3 y 50 caracteres")
    return value


def validate_future_datetime(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed <= datetime.now(timezone.utc):
            raise ValueError("La fecha de expiracion debe ser futura")
        return parsed.isoformat()
    except ValueError as exc:
        raise ValueError(f"Formato de fecha invalido: {exc}") from exc


class CreateURLRequest(BaseModel):
    url: str
    alias: Optional[str] = None
    expires_at: Optional[str] = None

    @field_validator("alias")
    @classmethod
    def alias_valid(cls, value: Optional[str]) -> Optional[str]:
        return validate_alias(value)

    @field_validator("expires_at")
    @classmethod
    def expires_valid(cls, value: Optional[str]) -> Optional[str]:
        return validate_future_datetime(value)


class UpdateURLRequest(BaseModel):
    url: Optional[str] = None
    expires_at: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("expires_at")
    @classmethod
    def expires_valid(cls, value: Optional[str]) -> Optional[str]:
        return validate_future_datetime(value)


class URLResponse(BaseModel):
    alias: str
    original: str
    short_url: str
    created_at: str
    expires_at: Optional[str]
    click_count: int
    is_active: bool
