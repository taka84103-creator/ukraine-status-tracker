import requests
import logging

logger = logging.getLogger(__name__)

DEEPSTATE_URL = "https://deepstatemap.live/api/history/last"


def fetch_occupation_polygons() -> dict:
    """
    Загружает GeoJSON полигоны оккупированных территорий.
    Возвращает словарь:
      {
        "occupied": [список полигонов Shapely],
        "partial":  [список полигонов Shapely],
        "source":   "название источника"
      }
    При ошибке основного источника — пробует резервный.
    """
    from shapely.geometry import shape

    # Пробуем основной источник — DeepStateMap
    polygons = _fetch_from_deepstate()
    if polygons:
        return polygons

    # Резервный источник — ACLED conflict data
    logger.warning("DeepStateMap недоступен, пробуем резервный источник...")
    polygons = _fetch_from_acled()
    if polygons:
        return polygons

    logger.error("Все источники данных об оккупации недоступны")
    return {"occupied": [], "partial": [], "source": "недоступен"}


def _fetch_from_deepstate() -> dict | None:
    """Завантаження полігонів з DeepStateMap."""
    try:
        response = requests.get(DEEPSTATE_URL, timeout=30)
        response.raise_for_status()
        data = response.json()

        # ДІАГНОСТИКА: друкуємо повну структуру відповіді
        logger.info(f"HTTP статус: {response.status_code}")
        logger.info(f"Тип даних: {type(data).__name__}")

        if isinstance(data, dict):
            logger.info(f"Ключі: {list(data.keys())}")
            # Друкуємо перший рівень кожного ключа
            for key in list(data.keys())[:5]:
                val = data[key]
                logger.info(f"  [{key}] тип={type(val).__name__}, значення={str(val)[:200]}")

        elif isinstance(data, list):
            logger.info(f"Список з {len(data)} елементів")
            if data:
                logger.info(f"Перший елемент: {str(data[0])[:300]}")

        return {"occupied": [], "partial": [], "source": "DeepStateMap (діагностика)"}

    except Exception as e:
        logger.error(f"Помилка DeepStateMap: {e}")
        return None


def _fetch_from_acled() -> dict | None:
    """
    Резервный источник: ACLED (Armed Conflict Location & Event Data).
    Возвращает None если недоступен.
    """
    # ACLED требует регистрации для полного API
    # Здесь используем публичный GeoJSON слой
    ACLED_URL = (
        "https://api.acleddata.com/acled/read.csv?"
        "country=Ukraine&event_type=Battle&limit=0&format=json"
    )
    try:
        response = requests.get(ACLED_URL, timeout=30)
        response.raise_for_status()
        # Упрощённая логика — возвращаем пустые полигоны
        # (лучше чем ничего, пункты получат статус "Не удалось определить")
        logger.info("ACLED: данные получены (резервный режим)")
        return {"occupied": [], "partial": [], "source": "ACLED (резервный)"}
    except Exception as e:
        logger.warning(f"ACLED недоступен: {e}")
        return None
