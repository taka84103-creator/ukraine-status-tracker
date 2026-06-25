# Статусы населённых пунктів
STATUS_FREE = "Свободен"
STATUS_OCCUPIED = "Оккупирован"
STATUS_PARTIAL = "Частично оккупирован"
STATUS_UNKNOWN = "Не удалось определить"

# Цвета для условного форматирования (RGB 0-1)
COLOR_FREE     = {"red": 0.56, "green": 0.93, "blue": 0.56}  # зелёный
COLOR_OCCUPIED = {"red": 0.95, "green": 0.40, "blue": 0.40}  # красный
COLOR_PARTIAL  = {"red": 1.00, "green": 0.90, "blue": 0.40}  # жёлтый
COLOR_UNKNOWN  = {"red": 0.85, "green": 0.85, "blue": 0.85}  # серый

# Названия листов таблицы
SHEET_MAIN   = "Населённые пункты"
SHEET_SEARCH = "Поиск"
SHEET_INFO   = "Информация"

# Заголовки основного листа
HEADERS = [
    "Область", "Район", "Населённый пункт",
    "Тип", "Статус", "Дата обновления",
    "Широта", "Долгота", "Источник"
]

# Источники данных (в порядке приоритета)
DEEPSTATE_API = "https://deepstatemap.live/api/history/last"
OVERPASS_API  = "https://overpass-api.de/api/interpreter"
