from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from .db import db
from .security import verify_token


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    with db() as con:
        row = con.execute("SELECT * FROM users WHERE id=?", (payload.get("sub"),)).fetchone()
    if row is None or row["disabled"]:
        raise HTTPException(status_code=401, detail="user disabled or missing")
    return dict(row)


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    return user
