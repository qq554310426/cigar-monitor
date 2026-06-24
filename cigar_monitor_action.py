#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
古巴雪茄补货监控 - GitHub Actions 版
每次运行检查一次，通过 GitHub Actions 每 20 分钟自动运行
"""

import json
import os
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# ========== 配置 ==========
URL = "https://mrcigarshop.com/category/origin/cuban/"

# 从环境变量读取 Webhook（GitHub Secrets）
WEBHOOK_URL = os.environ.get(
    "WEBHOOK_URL",
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=8fb83904-8f1b-454e-b3fb-641f22124b63"
)
STATE_FILE = "cigar_stock_state.json"
# ===========================


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def parse_products(html_content):
    """解析页面 HTML"""
    soup = BeautifulSoup(html_content, "html.parser")
    cards = soup.select("div.wc-card.wc-card--grid")
    products = []

    for card in cards:
        is_oos = "wc-card--oos" in card.get("class", [])
        name_elem = card.select_one("h3.wc-card__name-heading a.wc-card__name")
        link_elem = name_elem if name_elem else card.select_one("a.wc-card__name")
        price_elem = card.select_one("span.wc-card__price")

        name = name_elem.get_text(strip=True) if name_elem else ""
        link = link_elem["href"] if link_elem and link_elem.get("href") else ""
        price = price_elem.get_text(strip=True) if price_elem else ""

        if name:
            products.append({
                "name": name,
                "link": link,
                "price": price,
                "stock_status": "out_of_stock" if is_oos else "in_stock",
            })

    return products


def fetch_page():
    """获取页面 - GitHub Actions 运行在美国服务器，不会被 403"""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        log(f"正在获取页面: {URL}")
        resp = requests.get(URL, headers=headers, timeout=30)
        log(f"HTTP 状态码: {resp.status_code}")

        if resp.status_code in (200, 202) and "wc-card" in resp.text:
            log(f"✅ 页面获取成功 ({len(resp.text)} 字节, {resp.text.count('wc-card')} 个卡片)")
            return resp.text
        else:
            log(f"❌ 页面获取失败: {resp.status_code}")
            return None
    except Exception as e:
        log(f"❌ 获取失败: {e}")
        return None


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(products):
    state = {}
    for p in products:
        state[p["name"]] = {
            "stock_status": p["stock_status"],
            "link": p["link"],
            "price": p["price"],
            "last_check": datetime.now().isoformat(),
        }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    log(f"状态已保存到 {STATE_FILE}")


def send_notification(changes):
    if not changes:
        return

    log(f"准备发送通知，共 {len(changes)} 个补货商品")
    log(f"Webhook URL: {WEBHOOK_URL[:60]}...")

    lines = [
        "🎉 古巴雪茄补货通知",
        "",
        f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"补货商品数量: {len(changes)}",
        "",
    ]

    for i, item in enumerate(changes, 1):
        lines.append(f"{i}. {item['name']}")
        if item.get("price"):
            lines.append(f"   价格: {item['price']}")
        if item.get("link"):
            lines.append(f"   链接: {item['link']}")
        lines.append("")

    lines.append("快去抢购吧！🚀")

    data = {"msgtype": "text", "text": {"content": "\n".join(lines)}}

    try:
        log(f"正在发送 POST 请求到企业微信...")
        resp = requests.post(WEBHOOK_URL, json=data, timeout=10)
        result = resp.json()
        log(f"企业微信响应: {result}")
        if result.get("errcode") == 0:
            log(f"✅ 通知发送成功 ({len(changes)} 个商品)")
        else:
            log(f"❌ 通知发送失败: {result}")
    except Exception as e:
        log(f"❌ 发送通知出错: {e}")


def main():
    log("=" * 50)
    log("古巴雪茄补货监控 - GitHub Actions 运行")
    log(f"WEBHOOK_URL 已配置: {bool(WEBHOOK_URL)}")
    log("=" * 50)

    # 获取页面
    html = fetch_page()
    if not html:
        log("获取页面失败，退出")
        return

    # 解析商品
    products = parse_products(html)
    log(f"解析到 {len(products)} 个商品")

    if not products:
        log("未解析到商品，退出")
        return

    # 加载上次状态
    prev = load_state()

    if not prev:
        log("首次运行，保存基准状态")
        save_state(products)
        out = sum(1 for p in products if p["stock_status"] == "out_of_stock")
        log(f"基准: 有货 {len(products) - out} 个, 缺货 {out} 个")
        # 首次运行也发一条启动通知
        send_startup_notification(products)
        return

    # 对比状态，找出补货
    changes = []
    for p in products:
        name = p["name"]
        if name in prev:
            if prev[name]["stock_status"] == "out_of_stock" and p["stock_status"] == "in_stock":
                changes.append(p)
                log(f"🎉 发现补货: {name}")
        else:
            log(f"ℹ️  新商品: {name}")

    # 保存当前状态
    save_state(products)

    # 发送通知
    if changes:
        log(f"发现 {len(changes)} 个补货商品，发送通知...")
        send_notification(changes)
    else:
        log("无补货，不发送通知")


def send_startup_notification(products):
    """首次运行时发送一条启动通知"""
    out = sum(1 for p in products if p["stock_status"] == "out_of_stock")
    lines = [
        "🚀 古巴雪茄监控已启动",
        "",
        f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"监控网站: mrcigarshop.com",
        f"商品总数: {len(products)}",
        f"有货: {len(products) - out} 个",
        f"缺货: {out} 个",
        "",
        "后续有补货时会立即通知您！",
    ]
    data = {"msgtype": "text", "text": {"content": "\n".join(lines)}}
    try:
        resp = requests.post(WEBHOOK_URL, json=data, timeout=10)
        result = resp.json()
        log(f"启动通知响应: {result}")
    except Exception as e:
        log(f"启动通知出错: {e}")


if __name__ == "__main__":
    main()
