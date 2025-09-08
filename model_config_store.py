import os
import sqlite3
import uuid
from typing import List, Optional, Dict, Any


def _connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS model_configs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    model TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 0 CHECK(is_active IN (0,1))
                );
                """
            )
            # Helpful index for quick active lookup
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_model_configs_active ON model_configs(is_active);"
            )
    finally:
        conn.close()


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return key[:2] + "****" + key[-2:]
    return key[:3] + "-****" + key[-4:]


def list_model_configs(db_path: str) -> List[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "SELECT id, name, base_url, model, api_key, is_active FROM model_configs ORDER BY name ASC"
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "base_url": r["base_url"],
                "model": r["model"],
                "api_key_masked": _mask_key(r["api_key"]),
                "is_active": bool(r["is_active"]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_model_config(db_path: str, config_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "SELECT id, name, base_url, model, api_key, is_active FROM model_configs WHERE id = ?",
            (config_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            "id": r["id"],
            "name": r["name"],
            "base_url": r["base_url"],
            "model": r["model"],
            "api_key": r["api_key"],
            "is_active": bool(r["is_active"]),
        }
    finally:
        conn.close()


def get_active_model_config(db_path: str) -> Optional[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "SELECT id, name, base_url, model, api_key FROM model_configs WHERE is_active = 1 LIMIT 1"
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            "id": r["id"],
            "name": r["name"],
            "base_url": r["base_url"],
            "model": r["model"],
            "api_key": r["api_key"],
        }
    finally:
        conn.close()


def create_model_config(
    db_path: str,
    name: str,
    base_url: str,
    model: str,
    api_key: str,
    is_active: bool = False,
) -> Dict[str, Any]:
    conn = _connect(db_path)
    try:
        with conn:
            config_id = str(uuid.uuid4())
            if is_active:
                conn.execute("UPDATE model_configs SET is_active = 0 WHERE is_active = 1")
            conn.execute(
                "INSERT INTO model_configs (id, name, base_url, model, api_key, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                (config_id, name, base_url, model, api_key, 1 if is_active else 0),
            )
        return {
            "id": config_id,
            "name": name,
            "base_url": base_url,
            "model": model,
            "api_key": api_key,
            "is_active": is_active,
        }
    finally:
        conn.close()


def update_model_config(
    db_path: str,
    config_id: str,
    name: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    fields = []
    values: List[Any] = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if base_url is not None:
        fields.append("base_url = ?")
        values.append(base_url)
    if model is not None:
        fields.append("model = ?")
        values.append(model)
    if api_key is not None:
        fields.append("api_key = ?")
        values.append(api_key)

    if not fields:
        # Nothing to update
        return get_model_config(db_path, config_id)

    conn = _connect(db_path)
    try:
        with conn:
            values.append(config_id)
            conn.execute(f"UPDATE model_configs SET {', '.join(fields)} WHERE id = ?", values)
        return get_model_config(db_path, config_id)
    finally:
        conn.close()


def activate_model_config(db_path: str, config_id: str) -> bool:
    conn = _connect(db_path)
    try:
        with conn:
            cur = conn.execute("SELECT 1 FROM model_configs WHERE id = ?", (config_id,))
            if not cur.fetchone():
                return False
            conn.execute("UPDATE model_configs SET is_active = 0 WHERE is_active = 1")
            conn.execute("UPDATE model_configs SET is_active = 1 WHERE id = ?", (config_id,))
        return True
    finally:
        conn.close()


def delete_model_config(db_path: str, config_id: str) -> bool:
    conn = _connect(db_path)
    try:
        with conn:
            cur = conn.execute("DELETE FROM model_configs WHERE id = ?", (config_id,))
            return cur.rowcount > 0
    finally:
        conn.close()


