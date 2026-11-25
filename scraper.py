import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup

SOURCE = "https://loteries.lotoquebec.com/fr/loteries/jeu/a-tirage/lotto-max/resultats"
CSV_PATH = Path(__file__).resolve().with_name("data.csv")
NUMBERS = [f"n{i}" for i in range(1, 8)]
DRAW_COLUMNS = ["date", *NUMBERS, "prize"]
CSV_COLUMNS = [*DRAW_COLUMNS, "odd_even", "consecutive", "repeats", "zone"]
EASTERN = ZoneInfo("America/Toronto")
# The Tuesday and Friday draws are checked from the next Eastern calendar day.
DRAW_WEEKDAYS = {1, 4}
FRENCH_MONTHS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)
DRAW_NUMBERS = re.compile(
    r"(?<![\d-])((?:[0-9]{1,2}\s*[-–]\s*){6}[0-9]{1,2})"
    r"\s*Complémentaire\s*(?:\(\s*C\s*\))?\s*([0-9]{1,2})(?!\d)",
    re.IGNORECASE,
)
PRIZE_AMOUNT = re.compile(r"([0-9]+(?:\s+[0-9]{3})*)\s*,\s*[0-9]{2}\s*\$")
RESULTS_HEADING = "résultats des tirages - lotto max"


def parse_draw(html, draw_date):
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find(
        "h1", string=lambda text: text and text.strip().casefold() == RESULTS_HEADING
    )
    if heading is None:
        heading = next(
            (h for h in soup.find_all("h1")
             if h.get_text(" ", strip=True).casefold() == RESULTS_HEADING),
            None,
        )
    if heading is None:
        raise ValueError("搵唔到 Lotto Max 結果標題")

    date_heading = heading.find_next("h2")
    expected = (
        rf"0?{draw_date.day}(?:er)?\s+"
        rf"{FRENCH_MONTHS[draw_date.month - 1]}\s+{draw_date.year}"
    )
    if date_heading is None or not re.fullmatch(
        expected, date_heading.get_text(" ", strip=True), re.IGNORECASE
    ):
        raise ValueError("結果頁日期同要求日期唔一致")

    # The first main result after the date precedes Extra and other games.
    text = " ".join(
        str(node).strip() for node in date_heading.next_elements
        if isinstance(node, str) and node.strip()
        and node.parent.name not in {"script", "style"}
    )
    match = DRAW_NUMBERS.search(text)
    if match is None:
        raise ValueError("搵唔到主號碼同特別號")

    numbers = sorted(int(number) for number in re.findall(r"[0-9]+", match[1]))
    bonus = int(match[2])
    if len(set([*numbers, bonus])) != 8 or not all(
        1 <= number <= 52 for number in [*numbers, bonus]
    ):
        raise ValueError("開獎號碼有重複或超出範圍")

    # Use the 7/7 prize from the current draw, before other games' tables.
    for row in date_heading.find_all_next("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
        if len(cells) < 3 or cells[0] != "7/7":
            continue
        amount = PRIZE_AMOUNT.search(cells[2])
        if amount is None or not re.fullmatch(r"[0-9]+", cells[1]):
            raise ValueError("讀唔到本期 7/7 獎金")
        jackpot = int(re.sub(r"\s+", "", amount[1])) * max(1, int(cells[1]))
        prize = f"${jackpot // 1_000_000}M" if jackpot % 1_000_000 == 0 else f"${jackpot:,}"
        return dict(zip(DRAW_COLUMNS, [draw_date.isoformat(), *numbers, prize]))

    raise ValueError("搵唔到本期 7/7 獎金")


def calculate_metrics(draws):
    previous = set()
    records = []
    for row in draws.sort_values("date").to_dict("records"):
        numbers = [int(row[column]) for column in NUMBERS]
        odd = sum(number % 2 for number in numbers)
        consecutive = sum(right - left == 1 for left, right in zip(numbers, numbers[1:]))
        current = set(numbers)
        zones = sorted({min((number - 1) // 10 + 1, 5) for number in numbers})

        row["odd_even"] = f"{odd}單 {7 - odd}雙"
        row["consecutive"] = f"{consecutive} 個連續"
        row["repeats"] = len(current & previous)
        row["zone"] = f"{len(zones)}個區 ({','.join(map(str, zones))})"
        previous = current
        records.append(row)

    return pd.DataFrame(records, columns=CSV_COLUMNS).iloc[::-1]


def save_csv(draws):
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=CSV_PATH.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        try:
            draws.to_csv(handle, index=False)
            handle.close()
            temporary.replace(CSV_PATH)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    existing = pd.read_csv(CSV_PATH, usecols=DRAW_COLUMNS, keep_default_na=False)
    dates = pd.to_datetime(existing["date"], format="%Y-%m-%d", errors="raise")
    if dates.empty or dates.isna().any():
        raise ValueError("現有 data.csv 必須有有效嘅開獎日期")

    latest = dates.max().date()
    cutoff = datetime.now(EASTERN).date() - timedelta(days=1)
    missing = [
        day.date() for day in pd.date_range(latest + timedelta(days=1), cutoff)
        if day.weekday() in DRAW_WEEKDAYS
    ]
    if not missing:
        print(f"未有下一期需要更新。CSV 最新一期：{latest}")
        return

    incoming = []
    with requests.Session() as session:
        for draw_date in missing:
            url = f"{SOURCE}/{draw_date.isoformat()}"
            print(f"讀取 {draw_date}：{url}", flush=True)
            try:
                response = session.get(url, timeout=(10, 20))
                response.raise_for_status()
                incoming.append(parse_draw(response.content, draw_date))
            except (requests.RequestException, ValueError) as exc:
                raise RuntimeError(f"{draw_date} 抓取失敗：{exc}") from exc

    merged = pd.concat([existing, pd.DataFrame(incoming)], ignore_index=True)
    save_csv(calculate_metrics(merged))
    print(f"已新增 {len(incoming)} 期。CSV 最新一期：{incoming[-1]['date']}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"更新失敗，保留原有 data.csv：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
