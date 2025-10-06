# ExplorerFinal/auth.py
"""
Per-user auth registry for ExplorerFinal.
- Stores salted+hashed passwords in: ReDNACoreDemo/data/users/auth.json
- API:
    user_has_password(user_id) -> bool
    set_password(user_id, raw_password, enforce_unique=True) -> (ok, msg)
    set_initial_password(user_id, raw_password, enforce_unique=True) -> (ok, msg)
    change_password(user_id, old_password, new_password, enforce_unique=True) -> (ok, msg)
    check_password(user_id, raw_password) -> bool
    find_user_by_password(raw_password) -> user_id | None
    password_in_use(raw_password) -> user_id | None
    list_users() -> dict[user_id -> hash]
"""

from __future__ import annotations
import json
import os
import hashlib
from pathlib import Path
from typing import Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent  # project root (ReDNA_Demos)
AUTH_PATH = ROOT / "ReDNACoreDemo" / "data" / "users" / "auth.json"
SALT = os.getenv("EXPLORER_AUTH_SALT", "dev-salt").encode("utf-8")


def _hash_pw(pw: str) -> str:
    h = hashlib.sha256()
    h.update(SALT)
    h.update(pw.encode("utf-8"))
    return h.hexdigest()


def _load_registry() -> Dict[str, str]:
    if AUTH_PATH.exists():
        try:
            return json.loads(AUTH_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_registry(reg: Dict[str, str]) -> None:
    AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTH_PATH.write_text(json.dumps(reg, indent=2))


def password_in_use(password: str) -> Optional[str]:
    """Return user_id that already uses this password (if any)."""
    reg = _load_registry()
    hpw = _hash_pw(password)
    for uid, stored in reg.items():
        if stored == hpw:
            return uid
    return None


def user_has_password(user_id: str) -> bool:
    reg = _load_registry()
    return str(user_id) in reg


def set_password(user_id: str, password: str, enforce_unique: bool = True) -> Tuple[bool, str]:
    """Create/overwrite a user's password (admin-style)."""
    if not user_id:
        return False, "User ID is required."
    if not password:
        return False, "Password is required."
    if enforce_unique:
        holder = password_in_use(password)
        if holder and holder != user_id:
            return False, f"Password already in use by user '{holder}'. Choose a different password."
    reg = _load_registry()
    reg[str(user_id)] = _hash_pw(password)
    _save_registry(reg)
    return True, "Password set."


def set_initial_password(user_id: str, password: str, enforce_unique: bool = True) -> Tuple[bool, str]:
    """
    Set a password for an existing user that currently has none (no 'old password' required).
    Fails if the user already has a password.
    """
    if user_has_password(user_id):
        return False, "User already has a password. Use Change password instead."
    return set_password(user_id, password, enforce_unique=enforce_unique)


def change_password(user_id: str, old_password: str, new_password: str, enforce_unique: bool = True) -> Tuple[bool, str]:
    """
    Change an existing user's password (requires current password),
    but if the user has no password on file yet, allow setting it directly.
    """
    if not user_has_password(user_id):
        return set_initial_password(user_id, new_password, enforce_unique=enforce_unique)

    reg_ok = check_password(user_id, old_password)
    if not reg_ok:
        return False, "Current password is incorrect."
    if enforce_unique:
        holder = password_in_use(new_password)
        if holder and holder != user_id:
            return False, f"Password already in use by user '{holder}'."
    reg = _load_registry()
    reg[str(user_id)] = _hash_pw(new_password)
    _save_registry(reg)
    return True, "Password changed."


def check_password(user_id: str, password: str) -> bool:
    reg = _load_registry()
    hpw = reg.get(str(user_id))
    return bool(hpw and hpw == _hash_pw(password))


def find_user_by_password(password: str) -> Optional[str]:
    return password_in_use(password)


def list_users() -> Dict[str, str]:
    """Admin/debug only; returns map of user_id -> hashed password."""
    return _load_registry()