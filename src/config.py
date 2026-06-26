# Статуси населених пунктів
STATUS_FREE     = "Вільний"
STATUS_OCCUPIED = "Окупований"
STATUS_PARTIAL  = "Частково окупований"
STATUS_UNKNOWN  = "Не вдалося визначити"

# Кольори для умовного форматування (RGB 0-1)
COLOR_FREE     = {"red": 0.56, "green": 0.93, "blue": 0.56}  # зелений
COLOR_OCCUPIED = {"red": 0.95, "green": 0.40, "blue": 0.40}  # червоний
COLOR_PARTIAL  = {"red": 1.00, "green": 0.90, "blue": 0.40}  # жовтий
COLOR_UNKNOWN  = {"red": 0.85, "green": 0.85, "blue": 0.85}  # сірий

# Назви аркушів
SHEET_MAIN = "Населені пункти"

# Заголовки основного аркуша
HEADERS = [
    "Область", "Район", "Населений пункт",
    "Тип", "Статус", "Дата оновлення"
]

# Джерела даних
DEEPSTATE_API = "https://deepstatemap.live/api/history/last"
OVERPASS_API  = "https://overpass-api.de/api/interpreter"
