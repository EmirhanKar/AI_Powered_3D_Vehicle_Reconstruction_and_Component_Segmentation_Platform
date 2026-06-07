"""
Populer araba boyalarini backend'e ekler.
Calistirmak icin: python add_colors.py
"""

import asyncio
import sys
import httpx

# Windows encoding fix
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_URL = "http://192.168.1.34:8000"

# Populer araba boyalari (isim + hex kodu)
COLORS = [
    {"name": "Beyaz Sedef",       "hex": "#F5F5F5"},
    {"name": "Siyah",             "hex": "#1C1C1C"},
    {"name": "Gumus Metalik",     "hex": "#C0C0C0"},
    {"name": "Koyu Gri",          "hex": "#4A4A4A"},
    {"name": "Acik Gri",          "hex": "#A8A8A8"},
    {"name": "Kirmizi",           "hex": "#CC0000"},
    {"name": "Bordo",             "hex": "#800020"},
    {"name": "Turuncu",           "hex": "#E85D04"},
    {"name": "Sari",              "hex": "#F5C518"},
    {"name": "Nardo Gri",         "hex": "#8D8D8D"},
    {"name": "Koyu Mavi",         "hex": "#003399"},
    {"name": "Acik Mavi",         "hex": "#4A90D9"},
    {"name": "Gece Mavisi",       "hex": "#1B2A4A"},
    {"name": "Yesil",             "hex": "#2D6A4F"},
    {"name": "Haki Yesil",        "hex": "#5F6B3C"},
    {"name": "Bronz",             "hex": "#8C6239"},
    {"name": "Kahverengi",        "hex": "#6B4226"},
    {"name": "Altin Sarisi",      "hex": "#C9A84C"},
    {"name": "Mor",               "hex": "#5B2C8D"},
    {"name": "Mat Siyah",         "hex": "#2C2C2C"},
]

async def add_colors():
    async with httpx.AsyncClient(timeout=15.0) as client:
        added = 0
        failed = 0
        
        for color in COLORS:
            try:
                resp = await client.post(
                    f"{BASE_URL}/plugins/colors",
                    json={"color_code": color["hex"]},
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 201:
                    data = resp.json()
                    print(f"[OK] Eklendi: {color['name']} ({color['hex']}) -> ID: {data.get('color_id')}")
                    added += 1
                else:
                    print(f"[HATA] {color['name']} ({color['hex']}) -> {resp.status_code}: {resp.text}")
                    failed += 1
            except Exception as e:
                print(f"[ISTISNA] {color['name']} -> {e}")
                failed += 1
        
        print(f"\n{'='*50}")
        print(f"Toplam: {len(COLORS)} renk")
        print(f"[OK] Basariyla eklendi: {added}")
        print(f"[HATA] Basarisiz: {failed}")

if __name__ == "__main__":
    asyncio.run(add_colors())
