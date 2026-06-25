import logging
import sys

# Настройка логирования — все сообщения будут видны в GitHub Actions
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 50)
    logger.info("Запуск обновления статусов населённых пунктов")
    logger.info("=" * 50)

    # Шаг 1: подключение к Google Sheets
    from sheets import connect_to_sheets, setup_spreadsheet, update_settlements
    spreadsheet = connect_to_sheets()
    setup_spreadsheet(spreadsheet)
    logger.info("✅ Подключение к Google Sheets установлено")

    # Шаг 2: загрузка населённых пунктов
    from settlements import fetch_settlements
    settlements = fetch_settlements()
    if not settlements:
        logger.error("❌ Не удалось загрузить населённые пункты. Обновление отменено.")
        sys.exit(1)
    logger.info(f"✅ Загружено {len(settlements)} населённых пунктов")

    # Шаг 3: загрузка полигонов оккупации
    from occupation import fetch_occupation_polygons
    polygons = fetch_occupation_polygons()
    logger.info(f"✅ Источник данных об оккупации: {polygons['source']}")

    # Шаг 4: определение статусов
    from geo_analysis import assign_statuses
    settlements = assign_statuses(settlements, polygons)
    logger.info("✅ Статусы определены")

    # Шаг 5: обновление таблицы
    update_settlements(spreadsheet, settlements)
    logger.info("✅ Таблица обновлена")

    logger.info("=" * 50)
    logger.info("Обновление завершено успешно")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
