# Общая структура проекта (файлы/папки и назначение)

- `main.py` — точка входа, инициализация БД и запуск `MainWindow`.
    
- `README.md` — инструкции по установке/запуску, замечания по swap_iv и профилям.
    
- `requirements.txt` — зависимости: `PySide6`, `pymodbus`, `pyserial`, `SQLAlchemy` и др.
    
- `resources.py` — пути к ресурсам, значения по умолчанию (RTU/TCP), переменная окружения `PC_DB_PATH`.
    
- `dictionary.py` — словари/строки интерфейса (подписи, сообщения).
    
- `app/`
    
    - `db.py` — работа с SQLite (создание таблицы `profiles`, CRUD для профилей).
        
    - `models.py` — SQLAlchemy модель `Profile` (см. замечание об inconsistency ниже).
        
    - `controllers/source_controller.py` — высокоуровневый контроллер: connect/disconnect, команды управления источником (set_power и пр.), связывает GUI ↔ Modbus сервис/драйвер.
        
    - `modbus/`
        
        - `client_factory.py` — создание клиента Modbus (RTU через `pymodbus.ModbusSerialClient` или TCP через `pymodbus.ModbusTcpClient`), нормализация названий COM-портов.
            
        - `connection_service.py` — сервис опроса (QTimer) — периодически вызывает драйвер для чтения измерений и эмитит сигналы `measurements` и `error`.
            
        - `driver.py` — `SourceDriver`: низкоуровневые методы чтения/записи регистров (read input/holding/coils, write coil/register), масштабирование, обработка signed/unsigned, логика автосвопа I/U.
            
        - `registry.py` — маппинг регистров (Coils, InputRegs, HoldingRegs), утилиты и `Measurements` dataclass.
            
    - `controllers/` — (пока один контроллер `source_controller.py`).
        
    - `gui/` — все экраны:
        
        - `main_window.py` — главный фрейм, сборка навигации, создание `AppStore` и `SourceController`.
            
        - `connection_tab.py`, `connection_type_screen.py`, `settings_panel.py`, `settings_screen.py` — экран подключения и управление профилями.
            
        - `left_nav.py`, `status_bar.py`, `widgets.py` — вспомогательные виджеты (AlertBox, индикаторы, иконки и пр.).
            
        - `style.qss` — стили приложения.
            
- `assets/` — SVG иконки и изображения.
    

# Подробный разбор компонентов и поток данных

### 1) Запуск приложения (`main.py`)

- Инициализирует БД (`init_db`), создаёт `QApplication`, инстанцирует `MainWindow` и запускает event loop.
    
- `MainWindow` создаёт `AppStore` (глобальное состояние) и `SourceController(store, self)`.
    

### 2) Состояние приложения (`app/state/store.py`)

- `AppStore` — `QObject` с сигналами:
    
    - `connectionChanged(bool)`,
        
    - `errorText(str)`,
        
    - `measurementsChanged(object)`.
        
- GUI подписывается на эти сигналы и обновляет виджеты.
    

### 3) Работа с профилями (локальная БД)

- `app/db.py`:
    
    - Использует `sqlite3`, по умолчанию создаёт `profiles` таблицу: `CREATE TABLE IF NOT EXISTS profiles ( ... )`.
        
    - Функции: `init_db`, `get_all_profiles`, `get_profile`, `save_profile`/`add_profile`, `update_profile`, `delete_profile`, `rename_profile`.
        
    - Поле `settings` хранит JSON-строку с параметрами подключения.
        
- `app/models.py` содержит SQLAlchemy модель `Profile` (см. замечание о несоответствии).
    

### 4) Создание Modbus-клиента (`client_factory.py`)

- На основании `conn_type` и `settings` возвращается:
    
    - `ModbusSerialClient` (RTU) с параметрами `port`, `baudrate`, `parity`, `stopbits` и `timeout`, или
        
    - `ModbusTcpClient` (TCP) с `host`, `port`.
        
- Проводится нормализация имени COM-порта (Windows строка из `list_ports` → `COMx`).
    

### 5) Драйвер прибора (`driver.py` + `registry.py`)

- `registry.py` — содержит адреса регистров (Coils, InputRegs, HoldingRegs) и `Measurements` dataclass.
    
- `SourceDriver`:
    
    - Внутренние методы чтения/записи: `_read_input_registers`, `_read_holding_registers`, `_read_coils`, `_write_register`, `_write_coil_raw`.
        
    - Утилиты: `_s16` (signed 16-bit), `u32_from_words` (склейка 32-бит), формы адресации (1-based → 0-based).
        
    - Масштабирование измерений: `SCALE_I = 0.1`, `SCALE_V = 0.1`.
        
    - Логика автосвопа `swap_iv` (если напряжение/ток перепутаны): есть auto-detect, а также возможность принудительной настройки.
        
    - `ping()` — проверка связи; `read_measurements()` — читает I/U и другие параметры; `set_output` / `write` — записывает управляющие значения в coils/holding regs.
        

### 6) Сервис опроса (`connection_service.py`)

- `ConnectionService` = `QObject` c `QTimer`. На тике вызывает `driver.read_measurements()` и эмитит сигнал `measurements` или `error`.
    
- Важное: опрос выполняется в контексте Qt main thread (через QTimer), т.е. Modbus вызовы блокирующие — см. замечания ниже.
    

### 7) Контроллер уровня GUI (`app/controllers/source_controller.py`)

- `SourceController`:
    
    - Получает `store` (AppStore), создаёт/держит `client`, `SourceDriver` и `ConnectionService`.
        
    - Методы: `connect(settings)`, `disconnect()`, `set_power(on/off)` и т.п.
        
    - При подключении: создаёт клиент через `client_factory`, создаёт `SourceDriver(client, unit_id)`, проверяет `ping()` и стартует `ConnectionService` (polling).
        
    - Обрабатывает ошибки и передаёт их в `store.set_error()`.
        

### 8) GUI (screens)

- `ConnectionTab` + `SettingsPanel`:
    
    - Формы для ввода RTU/TCP параметров, профильный dropdown (CRUD через `app.db`), кнопки подключиться/сохранить профиль.
        
    - Для RTU используются `serial.tools.list_ports` для списка портов.
        
- `MainWindow`:
    
    - Создаёт левую панель навигации и стек экранов, отображает заголовки, статус-бар, runtime таймер и индикаторы состояния (power ready/on/stop).
        
    - Подписывается на `store` сигналы и меняет UI accordingly.
        
- `widgets.AlertBox` и другие виджеты — для оповещений, анимаций и индикаторов.
