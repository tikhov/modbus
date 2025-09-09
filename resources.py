import os

# Базовая папка проекта (текущая директория файла resources.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Путь к базе данных (по умолчанию создаётся в корне проекта)
DB_PATH = os.environ.get("PC_DB_PATH", os.path.join(BASE_DIR, "profiles.db"))

# Папка с ресурсами (иконки, изображения интерфейса)
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")

# Словари с настройками по умолчанию
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
