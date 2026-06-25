import os
import json
import logging
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from config import (
    HEADERS, SHEET_MAIN, SHEET_SEARCH, SHEET_INFO,
    STATUS_FREE, STATUS_OCCUPIED, STATUS_PARTIAL, STATUS_UNKNOWN,
    COLOR_FREE, COLOR_OCCUPIED, COLOR_PARTIAL, COLOR_UNKNOWN
)

logger = logging.getLogger(__name__)

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


def connect_to_sheets() -> gspread.Spreadsheet:
    """Подключение к Google Sheets через сервисный аккаунт."""
    creds_json = os.environ["GOOGLE_CREDENTIALS"]
    spreadsheet_id = os.environ["SPREADSHEET_ID"]

    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)

    return client.open_by_key(spreadsheet_id)


def setup_spreadsheet(spreadsheet: gspread.Spreadsheet):
    """
    Первоначальная настройка таблицы:
    создаёт листы, заголовки, условное форматирование.
    Вызывается только если структура ещё не создана.
    """
    existing = [ws.title for ws in spreadsheet.worksheets()]

    # Создаём основной лист
    if SHEET_MAIN not in existing:
        ws = spreadsheet.add_worksheet(SHEET_MAIN, rows=50000, cols=9)
        ws.append_row(HEADERS, value_input_option="USER_ENTERED")
        _apply_formatting(spreadsheet, ws)
        logger.info(f"Создан лист '{SHEET_MAIN}'")

    # Создаём лист поиска
    if SHEET_SEARCH not in existing:
        ws_search = spreadsheet.add_worksheet(SHEET_SEARCH, rows=20, cols=9)
        _setup_search_sheet(ws_search)
        logger.info(f"Создан лист '{SHEET_SEARCH}'")

    # Создаём информационный лист
    if SHEET_INFO not in existing:
        ws_info = spreadsheet.add_worksheet(SHEET_INFO, rows=10, cols=2)
        ws_info.update("A1", [["Параметр", "Значение"]])
        logger.info(f"Создан лист '{SHEET_INFO}'")


def update_settlements(
    spreadsheet: gspread.Spreadsheet,
    settlements: list[dict]
):
    """
    Умное обновление — изменяет только те строки, где статус изменился.
    Не пересоздаёт таблицу целиком.
    """
    ws = spreadsheet.worksheet(SHEET_MAIN)
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    # Загружаем текущие данные для сравнения
    existing_data = ws.get_all_values()

    # Строим словарь: название → (номер строки, текущий статус)
    existing_map: dict[str, tuple[int, str]] = {}
    for i, row in enumerate(existing_data[1:], start=2):  # пропускаем заголовок
        if len(row) >= 5:
            key = f"{row[0]}|{row[2]}"  # область + название
            existing_map[key] = (i, row[4])  # строка, статус

    # Разделяем на новые и изменившиеся
    rows_to_append = []
    cells_to_update = []

    for s in settlements:
        key = f"{s['region']}|{s['name']}"
        row_data = [
            s["region"],
            s["district"],
            s["name"],
            s["place_type"],
            s["status"],
            now,
            s["lat"],
            s["lon"],
            s["source"],
        ]

        if key in existing_map:
            row_num, old_status = existing_map[key]
            if old_status != s["status"]:
                # Статус изменился — обновляем строку
                cells_to_update.append((row_num, row_data))
        else:
            # Новый населённый пункт — добавляем
            rows_to_append.append(row_data)

    # Применяем обновления батчами (эффективнее одиночных запросов)
    if cells_to_update:
        batch = []
        for row_num, row_data in cells_to_update:
            for col_idx, value in enumerate(row_data, start=1):
                batch.append({
                    "range": gspread.utils.rowcol_to_a1(row_num, col_idx),
                    "values": [[value]]
                })
        ws.batch_update(batch)
        logger.info(f"Обновлено {len(cells_to_update)} изменившихся записей")

    # Добавляем новые записи
    if rows_to_append:
        ws.append_rows(rows_to_append, value_input_option="USER_ENTERED")
        logger.info(f"Добавлено {len(rows_to_append)} новых записей")

    # Обновляем информационный лист
    _update_info_sheet(spreadsheet, len(settlements), now)


def _apply_formatting(spreadsheet: gspread.Spreadsheet, ws):
    """Настраивает условное форматирование цветов по статусу."""
    sheet_id = ws.id

    def color_rule(status: str, color: dict) -> dict:
        return {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": sheet_id, "startColumnIndex": 4, "endColumnIndex": 5}],
                    "booleanRule": {
                        "condition": {
                            "type": "TEXT_EQ",
                            "values": [{"userEnteredValue": status}]
                        },
                        "format": {"backgroundColor": color}
                    }
                },
                "index": 0
            }
        }

    requests = [
        color_rule(STATUS_FREE,     COLOR_FREE),
        color_rule(STATUS_OCCUPIED, COLOR_OCCUPIED),
        color_rule(STATUS_PARTIAL,  COLOR_PARTIAL),
        color_rule(STATUS_UNKNOWN,  COLOR_UNKNOWN),
    ]
    spreadsheet.batch_update({"requests": requests})


def _setup_search_sheet(ws):
    """Настраивает лист поиска с формулами."""
    ws.update("A1", [["Введите название населённого пункта:"]])
    ws.update("B1", [[""]])  # поле ввода
    ws.update("A3", [["Область", "Район", "Населённый пункт",
                       "Тип", "Статус", "Дата обновления", "Источник"]])

    # Формула поиска через QUERY
    search_formula = (
        f'=IFERROR(QUERY(\'{SHEET_MAIN}\'!A:I,'
        f'"SELECT A,B,C,D,E,F,I WHERE LOWER(C) CONTAINS LOWER("""&B1&""")",1),'
        f'"Не найдено")'
    )
    ws.update("A4", [[search_formula]], value_input_option="USER_ENTERED")


def _update_info_sheet(spreadsheet, total: int, updated_at: str):
    """Обновляет статистику на информационном листе."""
    ws = spreadsheet.worksheet(SHEET_INFO)
    ws.update("A1", [
        ["Параметр", "Значение"],
        ["Всего населённых пунктов", total],
        ["Последнее обновление", updated_at],
        ["Статус системы", "✅ Работает"],
    ])
