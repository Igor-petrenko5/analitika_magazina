"""Полный учебный пайплайн аналитики интернет-магазина."""
from __future__ import annotations

import argparse
from numbers import Number
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ОБЯЗАТЕЛЬНЫЕ_ПОЛЯ = ["user_id", "product_id", "action", "category", "price", "timestamp"]
ДЕЙСТВИЯ = {"view", "add_to_cart", "purchase"}
ПЕРЕВОД = {"view": "Просмотр", "add_to_cart": "Добавление в корзину", "purchase": "Покупка"}


def загрузить_и_проверить(путь: Path) -> pd.DataFrame:
    df = pd.read_csv(путь)
    отсутствуют = sorted(set(ОБЯЗАТЕЛЬНЫЕ_ПОЛЯ) - set(df.columns))
    if отсутствуют:
        raise ValueError(f"В CSV отсутствуют обязательные столбцы: {отсутствуют}")
    df = df[ОБЯЗАТЕЛЬНЫЕ_ПОЛЯ].copy()
    df["user_id"] = pd.to_numeric(df.user_id, errors="raise").astype("int64")
    df["product_id"] = pd.to_numeric(df.product_id, errors="raise").astype("int64")
    df["price"] = pd.to_numeric(df.price, errors="raise").astype("float64")
    df["timestamp"] = pd.to_datetime(df.timestamp, errors="raise")
    df["action"] = df.action.astype("string").str.strip()
    df["category"] = df.category.astype("string").str.strip()
    if df[ОБЯЗАТЕЛЬНЫЕ_ПОЛЯ].isna().any().any():
        raise ValueError("В обязательных полях найдены пустые значения")
    неизвестные = sorted(set(df.action) - ДЕЙСТВИЯ)
    if неизвестные:
        raise ValueError(f"Неизвестные типы действий: {неизвестные}")
    if (df.price < 0).any():
        raise ValueError("Цена не может быть отрицательной")
    return df


def рассчитать(df: pd.DataFrame):
    популярность = (df.groupby(["action", "product_id", "category"], as_index=False)
                      .size().rename(columns={"size": "количество_событий"}))
    популярность["действие"] = популярность.action.map(ПЕРЕВОД)
    топ = (популярность.sort_values(["action", "количество_событий", "product_id"],
                                   ascending=[True, False, True])
                      .groupby("action", group_keys=False).head(10))
    покупки = df[df.action.eq("purchase")]
    категории = (покупки.groupby("category", as_index=False)
                 .agg(покупки=("product_id", "size"), выручка=("price", "sum"))
                 .rename(columns={"category": "категория"}))
    категории["выручка"] = категории["выручка"].round(2)
    пары = (df.sort_values("timestamp")
            .groupby(["user_id", "product_id"], sort=False)
            .agg(просмотр=("timestamp", lambda s: s[df.loc[s.index, "action"].eq("view")].min()),
                 события=("action", list), времена=("timestamp", list)))
    воронка = []
    for просмотр, события, времена in пары.itertuples(index=False, name=None):
        if pd.isna(просмотр):
            continue
        воронка.append((просмотр, события, времена))
    просмотры = len(воронка)
    корзины = sum(any(a == "add_to_cart" and t > view_time
                      for a, t in zip(actions, times))
                  for view_time, actions, times in воронка)
    покупки_пары = 0
    for view_time, actions, times in воронка:
        cart_times = [t for a, t in zip(actions, times)
                      if a == "add_to_cart" and t > view_time]
        if cart_times:
            first_cart = min(cart_times)
            if any(a == "purchase" and t > first_cart for a, t in zip(actions, times)):
                покупки_пары += 1
    конверсии = pd.DataFrame([
        {"этап": "Просмотр → корзина", "пары_источник": просмотры,
         "пары_цель": корзины, "конверсия_%": round(100 * корзины / просмотры, 2) if просмотры else 0},
        {"этап": "Корзина → покупка", "пары_источник": корзины,
         "пары_цель": покупки_пары, "конверсия_%": round(100 * покупки_пары / корзины, 2) if корзины else 0},
        {"этап": "Просмотр → покупка", "пары_источник": просмотры,
         "пары_цель": покупки_пары, "конверсия_%": round(100 * покупки_пары / просмотры, 2) if просмотры else 0},
    ])
    итоги = pd.DataFrame([
        {"показатель": "Количество событий", "значение": len(df)},
        {"показатель": "Уникальные пользователи", "значение": df.user_id.nunique()},
        {"показатель": "Уникальные товары", "значение": df.product_id.nunique()},
        {"показатель": "Сумма выручки", "значение": round(float(покупки.price.sum()), 2)},
    ])
    return популярность, топ, категории, конверсии, итоги


def сохранить_excel(tables: list[tuple[str, pd.DataFrame]], path: Path) -> None:
    """Создаёт .xlsx стандартной библиотекой Python, без внешнего Excel-модуля."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg = "http://schemas.openxmlformats.org/package/2006/relationships"
    ct = "http://schemas.openxmlformats.org/package/2006/content-types"
    ET.register_namespace("", ns)
    ET.register_namespace("r", rel)

    def col_name(n: int) -> str:
        out = ""
        while n:
            n, rem = divmod(n - 1, 26)
            out = chr(65 + rem) + out
        return out

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        workbook = ET.Element(f"{{{ns}}}workbook")
        sheets = ET.SubElement(workbook, f"{{{ns}}}sheets")
        for i, (name, _) in enumerate(tables, 1):
            ET.SubElement(sheets, f"{{{ns}}}sheet", {"name": name, "sheetId": str(i), f"{{{rel}}}id": f"rId{i}"})
        archive.writestr("xl/workbook.xml", ET.tostring(workbook, encoding="utf-8", xml_declaration=True))
        relationships = ET.Element(f"{{{pkg}}}Relationships")
        for i, _ in enumerate(tables, 1):
            ET.SubElement(relationships, f"{{{pkg}}}Relationship", {"Id": f"rId{i}", "Type": f"{rel}/worksheet", "Target": f"worksheets/sheet{i}.xml"})
        ET.SubElement(relationships, f"{{{pkg}}}Relationship", {"Id": f"rId{len(tables)+1}", "Type": f"{rel}/styles", "Target": "styles.xml"})
        archive.writestr("xl/_rels/workbook.xml.rels", ET.tostring(relationships, encoding="utf-8", xml_declaration=True))
        types = ET.Element(f"{{{ct}}}Types")
        ET.SubElement(types, f"{{{ct}}}Default", {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"})
        ET.SubElement(types, f"{{{ct}}}Default", {"Extension": "xml", "ContentType": "application/xml"})
        ET.SubElement(types, f"{{{ct}}}Override", {"PartName": "/xl/workbook.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"})
        ET.SubElement(types, f"{{{ct}}}Override", {"PartName": "/xl/styles.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"})
        for i, _ in enumerate(tables, 1):
            ET.SubElement(types, f"{{{ct}}}Override", {"PartName": f"/xl/worksheets/sheet{i}.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"})
        archive.writestr("[Content_Types].xml", ET.tostring(types, encoding="utf-8", xml_declaration=True))
        styles = ET.Element(f"{{{ns}}}styleSheet")
        fonts = ET.SubElement(styles, f"{{{ns}}}fonts", {"count": "1"})
        font = ET.SubElement(fonts, f"{{{ns}}}font")
        ET.SubElement(font, f"{{{ns}}}sz", {"val": "11"}); ET.SubElement(font, f"{{{ns}}}name", {"val": "Calibri"})
        fills = ET.SubElement(styles, f"{{{ns}}}fills", {"count": "2"})
        ET.SubElement(ET.SubElement(fills, f"{{{ns}}}fill"), f"{{{ns}}}patternFill", {"patternType": "none"})
        ET.SubElement(ET.SubElement(fills, f"{{{ns}}}fill"), f"{{{ns}}}patternFill", {"patternType": "gray125"})
        borders = ET.SubElement(styles, f"{{{ns}}}borders", {"count": "1"})
        border = ET.SubElement(borders, f"{{{ns}}}border")
        for edge in ("left", "right", "top", "bottom", "diagonal"):
            ET.SubElement(border, f"{{{ns}}}{edge}")
        ET.SubElement(styles, f"{{{ns}}}cellStyleXfs", {"count": "1"}).append(ET.Element(f"{{{ns}}}xf", {"numFmtId": "0", "fontId": "0", "fillId": "0", "borderId": "0"}))
        ET.SubElement(styles, f"{{{ns}}}cellXfs", {"count": "1"}).append(ET.Element(f"{{{ns}}}xf", {"numFmtId": "0", "fontId": "0", "fillId": "0", "borderId": "0", "xfId": "0"}))
        cellstyles = ET.SubElement(styles, f"{{{ns}}}cellStyles", {"count": "1"})
        ET.SubElement(cellstyles, f"{{{ns}}}cellStyle", {"name": "Normal", "xfId": "0", "builtinId": "0"})
        archive.writestr("xl/styles.xml", ET.tostring(styles, encoding="utf-8", xml_declaration=True))
        for i, (_, frame) in enumerate(tables, 1):
            root = ET.Element(f"{{{ns}}}worksheet")
            sheetdata = ET.SubElement(root, f"{{{ns}}}sheetData")
            data = [list(frame.columns)] + frame.astype(object).where(pd.notna(frame), "").values.tolist()
            for ri, row in enumerate(data, 1):
                row_el = ET.SubElement(sheetdata, f"{{{ns}}}row", {"r": str(ri)})
                for ci, value in enumerate(row, 1):
                    cell = ET.SubElement(row_el, f"{{{ns}}}c", {"r": f"{col_name(ci)}{ri}"})
                    if hasattr(value, "item"):
                        value = value.item()
                    if isinstance(value, Number) and not isinstance(value, bool):
                        ET.SubElement(cell, f"{{{ns}}}v").text = str(value)
                    else:
                        cell.set("t", "inlineStr")
                        inline = ET.SubElement(cell, f"{{{ns}}}is")
                        ET.SubElement(inline, f"{{{ns}}}t").text = str(value)
            archive.writestr(f"xl/worksheets/sheet{i}.xml", ET.tostring(root, encoding="utf-8", xml_declaration=True))


def сохранить_отчёты(df, результаты, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    популярность, топ, категории, конверсии, итоги = результаты
    with sqlite3.connect(output / "analytics.db") as con:
        df.to_sql("events", con, if_exists="replace", index=False)
        con.execute("CREATE INDEX IF NOT EXISTS idx_events_action_product ON events(action, product_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_events_category ON events(category)")

    excel = output / "метрики_аналитики.xlsx"
    сохранить_excel([
        ("Итоги", итоги), ("Топ товаров", топ.drop(columns="action")),
        ("Выручка по категориям", категории), ("Конверсии", конверсии),
        ("Все товары", популярность.drop(columns="action")),
    ], excel)

    график1 = px.bar(популярность, x="product_id", y="количество_событий", color="действие",
                     facet_col="действие", facet_col_wrap=1,
                     labels={"product_id": "Товар", "количество_событий": "События", "действие": "Действие"},
                     title="Популярность товаров по типу действия")
    график2 = px.bar(категории.sort_values("выручка", ascending=True), x="выручка", y="категория",
                     orientation="h", text="выручка", title="Выручка по категориям",
                     labels={"выручка": "Выручка", "категория": "Категория"})
    funnel_values = [int(конверсии.iloc[0].пары_источник), int(конверсии.iloc[0].пары_цель),
                     int(конверсии.iloc[1].пары_цель)]
    график3 = go.Figure(go.Funnel(y=["Пары с просмотром", "Просмотр → корзина", "Корзина → покупка"],
                                  x=funnel_values,
                                  textinfo="value+percent initial"))
    график3.update_layout(title="Последовательная воронка по парам пользователь–товар", xaxis_title="Пар")
    html = "\n".join(fig.to_html(full_html=False, include_plotlyjs="cdn")
                      for fig in (график1, график2, график3))
    summary = итоги.to_html(index=False, border=0, classes="данные")
    conversion_table = конверсии.to_html(index=False, border=0, classes="данные")
    (output / "отчёт.html").write_text(
        "<!doctype html><html lang='ru'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
        "<title>Аналитика интернет-магазина</title><style>body{font:16px system-ui;max-width:1200px;margin:32px auto;padding:0 18px;color:#202b3c}"
        "h1{color:#17365d}.данные{border-collapse:collapse}.данные td,.данные th{padding:9px 14px;border-bottom:1px solid #ddd}</style>"
        f"<h1>Аналитика действий пользователей</h1><h2>Сводные показатели</h2>{summary}"
        f"<h2>Конверсии по последовательным действиям</h2>{conversion_table}{html}</html>",
        encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Аналитика действий пользователей магазина")
    parser.add_argument("--input", type=Path, required=True, help="Путь к CSV")
    parser.add_argument("--output", type=Path, default=Path("output"), help="Каталог результатов")
    args = parser.parse_args()
    df = загрузить_и_проверить(args.input)
    результаты = рассчитать(df)
    сохранить_отчёты(df, результаты, args.output)
    print(f"Готово: обработано {len(df):,} событий. Результаты: {args.output.resolve()}")


if __name__ == "__main__":
    main()
