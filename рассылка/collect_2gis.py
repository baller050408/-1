#!/usr/bin/env python3
"""
Сбор контактов компаний из 2ГИС через официальный Places API.

Оставляет только компании, у которых НЕТ сайта и НЕТ Telegram,
но ЕСТЬ email. Результат: emails.csv (почта, название, адрес, телефон, рубрика).

Ключ API: https://dev.2gis.com (бесплатный демо-ключ на тестовый период).

Пример:
    python3 collect_2gis.py --key ВАШ_КЛЮЧ --city "Казань" \
        --query "салон красоты" --query "автосервис" --query "стоматология"
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

API = "https://catalog.api.2gis.com/3.0/items"
FIELDS = "items.contact_groups,items.address,items.rubrics,items.full_name"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emails.csv")
TG_MARKERS = ("t.me/", "telegram.me/", "telegram.org/")


def fetch(params):
    url = API + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def parse_contacts(item):
    emails, phones, has_site, has_tg = [], [], False, False
    for group in item.get("contact_groups") or []:
        for c in group.get("contacts") or []:
            t = (c.get("type") or "").lower()
            v = (c.get("value") or c.get("text") or c.get("url") or "").strip()
            low = v.lower()
            if t == "email" and v:
                emails.append(v)
            elif t == "phone":
                phones.append(c.get("text") or v)
            elif t == "telegram" or any(m in low for m in TG_MARKERS):
                has_tg = True
            elif t == "website":
                has_site = True
    return emails, phones, has_site, has_tg


def collect(key, city, query, max_pages, page_size):
    rows = []
    for page in range(1, max_pages + 1):
        try:
            data = fetch({"q": f"{query} {city}", "type": "branch", "fields": FIELDS,
                          "page": page, "page_size": page_size, "key": key})
        except Exception as e:
            print(f"  ошибка запроса: {e}", file=sys.stderr)
            break
        meta = data.get("meta", {})
        if meta.get("code") != 200:
            print(f"  API: {meta.get('error', {}).get('message', meta)}", file=sys.stderr)
            break
        items = data.get("result", {}).get("items", [])
        if not items:
            break
        for it in items:
            emails, phones, has_site, has_tg = parse_contacts(it)
            if emails and not has_site and not has_tg:
                rubric = ", ".join(r.get("name", "") for r in it.get("rubrics") or [])
                for e in emails:
                    rows.append({"email": e.lower(), "название": it.get("name", ""),
                                 "адрес": it.get("full_name") or it.get("address_name", ""),
                                 "телефон": "; ".join(phones), "рубрика": rubric,
                                 "город": city, "запрос": query})
        total = data.get("result", {}).get("total", 0)
        if page * page_size >= total:
            break
        time.sleep(0.5)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--key", default=os.environ.get("DGIS_KEY"), help="ключ API 2ГИС (или env DGIS_KEY)")
    ap.add_argument("--city", action="append", required=True, help="город, можно несколько раз")
    ap.add_argument("--query", action="append", required=True, help="сфера бизнеса, можно несколько раз")
    ap.add_argument("--pages", type=int, default=5, help="сколько страниц на запрос (по умолчанию 5)")
    ap.add_argument("--page-size", type=int, default=10, help="результатов на страницу (демо-ключ: до 10)")
    a = ap.parse_args()
    if not a.key:
        sys.exit("Нужен ключ: --key или переменная окружения DGIS_KEY")

    existing = {}
    if os.path.exists(OUT):
        with open(OUT, newline="", encoding="utf-8") as f:
            existing = {r["email"]: r for r in csv.DictReader(f)}

    for city in a.city:
        for q in a.query:
            print(f"[{city}] {q} ...")
            for r in collect(a.key, city, q, a.pages, a.page_size):
                existing.setdefault(r["email"], r)

    cols = ["email", "название", "адрес", "телефон", "рубрика", "город", "запрос"]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(existing.values())
    with open(os.path.splitext(OUT)[0] + ".txt", "w", encoding="utf-8") as f:
        f.write("\n".join(existing.keys()) + "\n")
    print(f"Готово: {len(existing)} уникальных почт -> {OUT}")


if __name__ == "__main__":
    main()
