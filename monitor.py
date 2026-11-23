
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

        # 只处理明确标注年付的套餐
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

        # 必须有明确库存状态，不猜测
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

    if not results:
        raise RuntimeError(
            "没有找到可识别的套餐库存信息，可能页面结构变化或访问受限。"
        )

    return results


def send_wechat(title, content):
    response = requests.post(
        f"https://sctapi.ftqq.com/{KEY}.send",
        data={"title": title, "desp": content},
        timeout=20
    )
    response.raise_for_status()
    result = response.json()

    if result.get("code") != 0:
        raise RuntimeError("Server酱推送失败：" + str(result))


def main():
    current = get_stock()

    old = {}
    if STATE_FILE.exists():
        old = json.loads(STATE_FILE.read_text(encoding="utf-8"))

    alerts = []

    for name, item in current.items():
        was_available = old.get(name, {}).get("available", False)

        if item["available"] and not was_available:
            alerts.append(
                f"套餐：{name}\n价格：${item['price']}/年"
            )

    if alerts:
        send_wechat(
            "DMIT洛杉矶VPS补货提醒",
            "\n\n".join(alerts) +
            "\n\n请尽快前往DMIT官网核实库存和购买价格。"
        )

    STATE_FILE.write_text(
        json.dumps(current, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("扫描完成，识别套餐：", len(current))
    print("新发现有货套餐：", len(alerts))


if __name__ == "__main__":
    main()
