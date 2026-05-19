#!/usr/bin/env python3
"""
Script to fetch UVA data from Argentina Datos API
https://api.argentinadatos.com/v1/finanzas/indices/uva

To run:
    python -m etl.utils.fetch_uva
"""

from .utils import try_fetch, BROWSER_HEADERS


def fetch_uva_data():
    """
    Fetches UVA historical data from Argentina Datos API
    
    Returns:
        List of dictionaries with format: [{'date': 'YYYY-MM-DD', 'rate': float}, ...]
        Ready to be inserted into fx_rate table
    """
    url = "https://api.argentinadatos.com/v1/finanzas/indices/uva"
    resp = try_fetch(url, headers=BROWSER_HEADERS)
    
    if isinstance(resp, Exception):
        print(f"❌ Request error: {resp}")
        return []

    if resp.status_code != 200:
        print(f"❌ HTTP Error {resp.status_code}")
        print(f"Response text (first 300 chars):\n{resp.text[:300]}")
        return []

    try:
        raw_data = resp.json()
    except Exception as e:
        print(f"❌ Could not parse JSON: {e}")
        return []

    if not isinstance(raw_data, list):
        print(f"❌ Unexpected payload type: {type(raw_data)}")
        print(f"Payload preview: {str(raw_data)[:300]}")
        return []

    uva_data = []
    for i, item in enumerate(raw_data):
        if not isinstance(item, dict):
            continue

        fecha = item.get("fecha")
        valor = item.get("valor")

        if fecha is None or valor is None:
            print(f"⚠️ Skipping row {i}: missing fecha/valor -> {item}")
            continue

        try:
            rate = float(valor)
        except Exception:
            print(f"⚠️ Skipping row {i}: invalid valor -> {valor}")
            continue

        uva_data.append({
        "date": fecha,
        "value": rate
        })

    uva_data.sort(key=lambda x: x["date"])

    print(f"✅ Fetched {len(uva_data)} UVA records")
    return uva_data

if __name__ == "__main__":
    print("\n" + "🇦🇷" * 35)
    print("   UVA DATA FETCH SCRIPT - ARGENTINA DATOS API")
    print("🇦🇷" * 35 + "\n")
    
    data = fetch_uva_data()
    
    if data:
        print(f"\n📊 SAMPLE DATA:")
        print("="*70)
        print("First 5 records:")
        for item in data[:5]:
            print(f"  {item['date']} | Rate: ${item['value']:.2f}")
        print("\nLast 5 records:")
        for item in data[-5:]:
            print(f"  {item['date']} | Rate: ${item['value']:.2f}")
        print("="*70 + "\n")
