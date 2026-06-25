import logging
from shapely.geometry import Point
from config import STATUS_FREE, STATUS_OCCUPIED, STATUS_PARTIAL, STATUS_UNKNOWN

logger = logging.getLogger(__name__)


def determine_status(lat: float, lon: float, polygons: dict) -> str:
    if not lat or not lon or lat == 0 or lon == 0:
        return STATUS_UNKNOWN

    point = Point(lon, lat)  # Shapely: сначала долгота, потом широта

    # Проверка оккупированных территорий
    for polygon in polygons.get("occupied", []):
        try:
            if polygon.contains(point):
                return STATUS_OCCUPIED
        except Exception:
            continue

    # Проверка частично оккупированных
    for polygon in polygons.get("partial", []):
        try:
            if polygon.contains(point):
                return STATUS_PARTIAL
        except Exception:
            continue

    return STATUS_FREE


def assign_statuses(settlements: list[dict], polygons: dict) -> list[dict]:
    """
    Присваивает статус каждому населённому пункту из списка.
    Возвращает обновлённый список.
    """
    source = polygons.get("source", "неизвестен")
    total  = len(settlements)

    occupied_count = 0
    partial_count  = 0
    free_count     = 0

    for i, settlement in enumerate(settlements):
        status = determine_status(
            settlement["lat"],
            settlement["lon"],
            polygons
        )
        settlement["status"] = status
        settlement["source"] = source

        if status == STATUS_OCCUPIED: occupied_count += 1
        elif status == STATUS_PARTIAL: partial_count += 1
        elif status == STATUS_FREE:    free_count += 1

        # Логируем прогресс каждые 1000 записей
        if (i + 1) % 1000 == 0:
            logger.info(f"Обработано {i+1}/{total}...")

    logger.info(
        f"Итого: {free_count} свободных, "
        f"{occupied_count} оккупированных, "
        f"{partial_count} частично оккупированных"
    )
    return settlements
