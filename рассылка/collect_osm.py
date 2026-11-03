#!/usr/bin/env python3
"""
Сбор почт организаций из OpenStreetMap (Overpass API) — бесплатно, без ключа.

Берёт объекты с email, у которых НЕТ сайта и НЕТ Telegram.
Дописывает результат в emails.csv / emails.txt (общая база с collect_2gis.py).

Пример:
    python3 collect_osm.py --city "Казань" --city "Самара"
"""
import argparse
import csv
import json
import os
import sys
import urllib.parse
import urllib.request

SERVERS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emails.csv")
COLS = ["email", "название", "адрес", "телефон", "рубрика", "город", "запрос"]
SITE_KEYS = ("website", "contact:website", "url", "contact:telegram", "telegram")


def query(city):
    q = f"""
    [out:json][timeout:180];
    area["name"="{city}"]["place"~"city|town"]->.a;
    (
      nwr(area.a)["email"];
      nwr(area.a)["contact:email"];
    );
    out tags center;
    """
    data = urllib.parse.urlencode({"data": q}).encode()
    last = None
    for s in SERVERS:
        try:
            req = urllib.request.Request(s, data=data, headers={"User-Agent": "rassylka-collector/1.0"})
            with urllib.request.urlopen(req, timeout=200) as r:
                return json.load(r).get("elements", [])
        except Exception as e:
            last = e
    raise RuntimeError(last)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--city", action="append", required=True, help="город, можно несколько раз")
    a = ap.parse_args()

    base = {}
    if os.path.exists(OUT):
        with open(OUT, newline="", encoding="utf-8") as f:
            base = {r["email"]: r for r in csv.DictReader(f)}

    for city in a.city:
        print(f"[{city}] OpenStreetMap ...")
        try:
            elements = query(city)
        except Exception as e:
            print(f"  ошибка: {e}", file=sys.stderr)
            continue
        added = 0
        for el in elements:
            t = el.get("tags", {})
            if any(t.get(k) for k in SITE_KEYS):
                continue
            if "t.me/" in " ".join(t.values()).lower():
                continue
            raw = t.get("email") or t.get("contact:email") or ""
            addr = ", ".join(x for x in (t.get("addr:street"), t.get("addr:housenumber")) if x)
            rubric = t.get("shop") or t.get("amenity") or t.get("craft") or t.get("office") or t.get("tourism") or ""
            for e in [x.strip().lower() for x in raw.replace(",", ";").split(";") if "@" in x]:
                if e not in base:
                    base[e] = {"email": e, "название": t.get("name", ""), "адрес": addr,
                               "телефон": t.get("phone") or t.get("contact:phone", ""),
                               "рубрика": rubric, "город": city, "запрос": "osm"}
                    added += 1
        print(f"  найдено новых: {added}")

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(base.values())
    with open(os.path.splitext(OUT)[0] + ".txt", "w", encoding="utf-8") as f:
        f.write("\n".join(base.keys()) + "\n")
    print(f"Всего в базе: {len(base)} -> {OUT}")


if __name__ == "__main__":
    main()
