from __future__ import annotations

import secrets

COOKIE_NAME = "snake_uid"


class CookieUserService:
    """Issues a unique user ID per browser via a cookie."""

    def __init__(self, cookie_name: str = COOKIE_NAME) -> None:
        self._cookie_name = cookie_name

    @property
    def cookie_name(self) -> str:
        return self._cookie_name

    def new_id(self) -> str:
        return secrets.token_hex(16)

    def resolve(self, cookie_value: str | None) -> str:
        """Return the cookie's user ID, or mint a fresh one."""
        if cookie_value:
            return cookie_value
        return self.new_id()
