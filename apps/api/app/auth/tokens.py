from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pydantic import BaseModel, ValidationError

from app.core.settings import Settings

ALGORITHM = "HS256"


class TokenClaims(BaseModel):
    sub: UUID
    exp: datetime
    iat: datetime


def create_access_token(user_id: UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.session_secret.get_secret_value(), algorithm=ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> TokenClaims:
    try:
        payload = jwt.decode(
            token,
            settings.session_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
        return TokenClaims.model_validate(payload)
    except (jwt.PyJWTError, ValidationError) as exc:
        raise ValueError("invalid or expired access token") from exc
