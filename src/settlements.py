import json
import logging
import os
from config import STATUS_UNKNOWN

logger = logging.getLogger(__name__)

# Шлях до файлу в репозиторії
KOATUU_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "koatuu.json")

# Мапінг категорій → тип населеного пункту
KOATUU_TYPE_MAP = {
    "М":   "Місто",
    "Т":   "Селище міського типу",
    "С":   "Село",
    "Х":   "Хутір",
    "СМТ": "Селище міського типу",
    "СЩ":  "Селище",
}


def fetch_settlements() -> list[dict]:
    """
    Читає koatuu.json з репозиторію та повертає список населених пунктів.
    Структура файлу:
      Перший рівень  — область
      Другий рівень  — район/група
      Третій рівень  — рада/громада
      Четвертий рівень — населений пункт
    Населені пункти — це рядки де заповнений Четвертий рівень і є Категорія.
    """
    try:
        with open(KOATUU_FILE, encoding="utf-8") as f:
            data = json.load(f)

        logger.info(f"Файл koatuu.json завантажено: {len(data)} записів")

        # Збираємо назви областей за кодом першого рівня
        regions = {}
        for item in data:
            first  = item.get("Перший рівень", "").strip()
            second = item.get("Другий рівень", "").strip()
            third  = item.get("Третій рівень", "").strip()
            fourth = item.get("Четвертий рівень", "").strip()
            name   = item.get("Назва об'єкта українською мовою", "").strip()
            cat    = item.get("Категорія", "").strip()

            # Область: є тільки перший рівень, решта порожні, немає категорії
            if first and not second and not third and not fourth and not cat:
                regions[first] = _normalize_region(name)

        logger.info(f"Знайдено областей: {len(regions)}")

        # Збираємо населені пункти — рядки з заповненим четвертим рівнем і категорією
        settlements = []
        seen = set()

        for item in data:
            first  = item.get("Перший рівень", "").strip()
            second = item.get("Другий рівень", "").strip()
            third  = item.get("Третій рівень", "").strip()
            fourth = item.get("Четвертий рівень", "").strip()
            name   = item.get("Назва об'єкта українською мовою", "").strip()
            cat    = item.get("Категорія", "").strip()

            # Населений пункт: є четвертий рівень і категорія
            if not fourth or not cat:
                continue

            # Пропускаємо службові записи без реальної назви
            if not name or name.startswith("СЕЛО ") and len(name) < 6:
                continue

            place_type = KOATUU_TYPE_MAP.get(cat.upper(), "Інший")
            region     = regions.get(first, "")

            # Унікальний ключ щоб уникнути дублікатів
            key = f"{fourth}|{name.lower()}"
            if key in seen:
                continue
            seen.add(key)

            settlements.append({
                "name":       _title_case(name),
                "region":     region,
                "district":   "",   # район визначимо окремо якщо потрібно
                "place_type": place_type,
                "lat":        0,
                "lon":        0,
                "status":     STATUS_UNKNOWN,
            })

        logger.info(f"Населених пунктів після обробки: {len(settlements)}")
        return settlements

    except FileNotFoundError:
        logger.error(f"Файл не знайдено: {KOATUU_FILE}")
        logger.error("Покладіть koatuu.json у папку data/ репозиторію")
        return []
    except Exception as e:
        logger.error(f"Помилка читання koatuu.json: {e}")
        return []


def _normalize_region(name: str) -> str:
    """ВОЛИНСЬКА ОБЛАСТЬ → Волинська область"""
    name = name.strip()
    # Прибираємо зайві слова типу "М.СІМФЕРОПОЛЬ" після слешу
    if "/" in name:
        name = name.split("/")[0].strip()
    return name.title()


def _title_case(name: str) -> str:
    """ЗЕЛЕНИЙ ГАЙ → Зелений Гай"""
    return name.title()
