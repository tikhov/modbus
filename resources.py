import os
import sys
from pathlib import Path

def _is_frozen():
    """Возвращает True, если приложение запущено из .exe (PyInstaller)."""
    return getattr(sys, 'frozen', False)

def _get_base_dir():
    """Возвращает корень проекта — для исходников или для .exe."""
    if _is_frozen():
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))

def _get_persistent_dir():
    """Возвращает постоянную папку в пользовательском профиле (для БД и настроек)."""
    if _is_frozen():
        appdata = os.getenv('APPDATA')
        if appdata:
            return Path(appdata) / "PowerController"
        else:
            return Path.home() / "AppData" / "Roaming" / "PowerController"
    else:
        # В режиме разработки — БД в корне проекта
        return Path(_get_base_dir())

# === Пути ===
BASE_DIR = _get_base_dir()
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")

# БД хранится в постоянной папке (в .exe) или в корне (в разработке)
DB_PATH = os.environ.get("PC_DB_PATH", str(_get_persistent_dir() / "profiles.db"))

# === Настройки по умолчанию ===
DEFAULT_RTU = {
    "port": "COM3",
    "baudrate": "9600",
    "parity": "N",
    "stopbits": "1",
    "unit_id": "1"
}

DEFAULT_WIFI = {
    "host": "192.168.1.100",
    "port": "502",
    "unit_id": "1"
}