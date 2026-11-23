
import os
import re
import json
import requests
from pathlib import Path
from bs4 import BeautifulSoup

URL = "https://dmitstock.com/region/lax/"
KEY = os.environ["SERVERCHAN_SENDKEY"]
STATE_FILE = Path("state.json")


def get_stock():
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; DMITStockMonitor/1.0)"
    }

    response = requests.get(URL, headers=headers, timeout=25)

    if response.status_code == 403:
        print("监控暂停：DMITStock 拒绝了 GitHub Actions 的访问。")
        print("没有获取到库存数据，本次不更新历史库存。")
        return None

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.find_all(["tr", "article", "li"])
    results = {}

    for row in rows:
        text = " ".join(row.stripped_strings)
        low = text.lower()

        if "dmit" not in low:
            continue

        if not ("lax" in low or "los angeles" in low):
            continue

        if not any(x in low for x in [
            "annually", "annual", "yearly", "年付"
        ]):
            continue

        prices = re.findall(r"\$\s*(\d+(?:\.\d+)?)", text)

        if not prices:
            continue

        price = float(prices[0])

        if price > 50:
            continue

        sold_out = any(x in low for x in [
            "无货", "缺货", "sold out", "out of stock"
        ])

        available = any(x in low for x in [
            "有货", "in stock", "available"
        ]) and not sold_out

        if not (sold_out or available):
            continue

        name = text[:180]

        results[name] = {
            "price": price,
            "available": available
        }

    return results


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    return {}


def save_state(data):
    STATE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def send_message(title, content):
    url = f"https://sctapi.ftqq.com/{KEY}.send"

    response = requests.post(
        url,
        data={
            "title": title,
            "desp": content
        },
        timeout=20
    )

    response.raise_for_status()
    print("Server酱通知已发送。")


def main():
    current = get_stock()

    if current is None:
        return

    previous = load_state()

    if not previous:
        save_state(current)
        print("首次运行：已保存当前库存，不发送通知。")
        return

    messages = []

    for name, item in current.items():
        old = previous.get(name)

        if old is None:
            if item["available"]:
                messages.append(f"发现新套餐：{name}")
            continue

        if not old.get("available") and item["available"]:
            messages.append(f"套餐补货：{name}")

    if messages:
        send_message(
            "DMIT LAX 年付套餐库存提醒",
            "\n\n".join(messages)
        )
    else:
        print("没有发现新的补货。")

    save_state(current)


if __name__ == "__main__":
    main()
