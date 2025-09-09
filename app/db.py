# app/db.py
from __future__ import annotations
import os, json, sqlite3
from typing import Any, Dict, List, Optional

# По умолчанию кладём БД рядом с модулем
_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "profiles.sqlite3")
_DB_PATH = _DEFAULT_DB


def init_db(db_path: Optional[str] = None) -> None:
    """
    Инициализация SQLite-хранилища. Безопасно вызывать при старте.
    Можно передать путь к БД, иначе берём app/profiles.sqlite3.
    """
    global _DB_PATH
    if db_path:
        _DB_PATH = db_path

    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                name TEXT PRIMARY KEY,
                conn_type TEXT NOT NULL,          -- 'RTU' | 'TCP'
                settings TEXT NOT NULL            -- JSON-строка
            )
        """)
        conn.commit()


def _conn():
    return sqlite3.connect(_DB_PATH)


def _row_to_obj(row) -> Dict[str, Any]:
    # row: (name, conn_type, settings_json)
    return {
        "name": row[0],
        "conn_type": row[1],
        "settings": json.loads(row[2]) if row[2] else {}
    }


def get_all_profiles() -> List[Dict[str, Any]]:
    with _conn() as conn:
        cur = conn.execute("SELECT name, conn_type, settings FROM profiles ORDER BY name COLLATE NOCASE")
        return [_row_to_obj(r) for r in cur.fetchall()]


def get_profile_by_name(name: str) -> Optional[Dict[str, Any]]:
    name = (name or "").strip()
    if not name:
        return None
    with _conn() as conn:
        cur = conn.execute("SELECT name, conn_type, settings FROM profiles WHERE name = ?", (name,))
        row = cur.fetchone()
        return _row_to_obj(row) if row else None


def create_profile(name: str, conn_type: str, settings: Dict[str, Any]) -> None:
    """
    Создаёт профиль. Если имя уже существует — перезапишет (replace).
    """
    name = name.strip()
    settings_json = json.dumps(dict(settings or {}), ensure_ascii=False)
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO profiles(name, conn_type, settings) VALUES (?, ?, ?)",
            (name, conn_type, settings_json)
        )
        conn.commit()


def update_profile(name: str, conn_type: str, settings: Dict[str, Any]) -> None:
    """
    Обновляет существующий профиль. Если нет — создаёт.
    """
    name = (name or "").strip()
    settings_json = json.dumps(dict(settings or {}), ensure_ascii=False)
    with _conn() as conn:
        # попробуем UPDATE, если затронуто 0 строк — сделаем INSERT
        cur = conn.execute(
            "UPDATE profiles SET conn_type = ?, settings = ? WHERE name = ?",
            (conn_type, settings_json, name)
        )
        if cur.rowcount == 0:
            conn.execute(
                "INSERT INTO profiles(name, conn_type, settings) VALUES (?, ?, ?)",
                (name, conn_type, settings_json)
            )
        conn.commit()


def delete_profile(name: str) -> None:
    name = (name or "").strip()
    with _conn() as conn:
        conn.execute("DELETE FROM profiles WHERE name = ?", (name,))
        conn.commit()


def rename_profile(old_name: str, new_name: str) -> None:
    """
    Переименовывает профиль. Если новый уже есть — будет REPLACE новым содержимым старого.
    """
    old_name = (old_name or "").strip()
    new_name = (new_name or "").strip()
    if not old_name or not new_name or old_name == new_name:
        return

    with _conn() as conn:
        cur = conn.execute("SELECT conn_type, settings FROM profiles WHERE name = ?", (old_name,))
        row = cur.fetchone()
        if not row:
            return
        conn_type, settings_json = row

        # Удалим старый, вставим (или заменим) новый
        conn.execute("DELETE FROM profiles WHERE name = ?", (old_name,))
        conn.execute(
            "INSERT OR REPLACE INTO profiles(name, conn_type, settings) VALUES (?, ?, ?)",
            (new_name, conn_type, settings_json)
        )
        conn.commit()
