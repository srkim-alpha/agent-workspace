"""
Currency Checker Skill Module (skills/currency_checker.py)
-----------------------------------------------------------
Lightweight currency exchange rate fetcher using open-source Frankfurter / Open Exchange Rates API.
Supports USD, JPY (100 Yen), EUR to KRW conversions with built-in failover fallback.
"""

import sys
import json
import urllib.request
from datetime import datetime

# Configure UTF-8 encoding for standard output if supported
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


PRIMARY_ENDPOINT = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=KRW,JPY,EUR"
FALLBACK_ENDPOINT = "https://open.er-api.com/v6/latest/USD"


def get_exchange_rates(base_currency: str = "USD") -> dict:
    """
    Fetches real-time exchange rates for USD, JPY (100 Yen equivalent), and EUR relative to KRW.

    Returns:
        dict: Containing USD_KRW, JPY_100_KRW, EUR_KRW rates, timestamp, and status.
    """
    result = {
        "status": "error",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": None,
        "USD_KRW": None,
        "JPY_100_KRW": None,
        "EUR_KRW": None,
    }

    # Attempt 1: Frankfurter API
    try:
        req = urllib.request.Request(
            PRIMARY_ENDPOINT,
            headers={"User-Agent": "Antigravity-CurrencyChecker/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                rates = data.get("rates", {})
                
                usd_krw = rates.get("KRW")
                usd_jpy = rates.get("JPY")
                usd_eur = rates.get("EUR")

                if usd_krw and usd_jpy and usd_eur:
                    # Calculate rates
                    jpy_100_krw = (usd_krw / usd_jpy) * 100
                    eur_krw = usd_krw / usd_eur

                    result.update({
                        "status": "success",
                        "source": "Frankfurter API (European Central Bank)",
                        "USD_KRW": round(usd_krw, 2),
                        "JPY_100_KRW": round(jpy_100_krw, 2),
                        "EUR_KRW": round(eur_krw, 2),
                    })
                    return result
    except Exception as e:
        result["error_primary"] = str(e)

    # Attempt 2: Fallback to Open ER API
    try:
        req = urllib.request.Request(
            FALLBACK_ENDPOINT,
            headers={"User-Agent": "Antigravity-CurrencyChecker/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                rates = data.get("rates", {})

                usd_krw = rates.get("KRW")
                usd_jpy = rates.get("JPY")
                usd_eur = rates.get("EUR")

                if usd_krw and usd_jpy and usd_eur:
                    jpy_100_krw = (usd_krw / usd_jpy) * 100
                    eur_krw = usd_krw / usd_eur

                    result.update({
                        "status": "success",
                        "source": "Open ER API (Fallback)",
                        "USD_KRW": round(usd_krw, 2),
                        "JPY_100_KRW": round(jpy_100_krw, 2),
                        "EUR_KRW": round(eur_krw, 2),
                    })
                    return result
    except Exception as e:
        result["error_fallback"] = str(e)

    return result


def print_formatted_summary():
    """Prints a user-friendly summary of real-time exchange rates."""
    data = get_exchange_rates()
    print("=" * 50)
    print(" [Real-Time Exchange Rates / 실시간 주요 통화 환율] ")
    print("=" * 50)
    print(f" Timestamp : {data['timestamp']}")
    print(f" Source    : {data.get('source', 'Unknown')}")
    print("-" * 50)

    if data["status"] == "success":
        print(f" USD / KRW     : {data['USD_KRW']:,} KRW")
        print(f" JPY / KRW(100): {data['JPY_100_KRW']:,} KRW")
        print(f" EUR / KRW     : {data['EUR_KRW']:,} KRW")
    else:
        print(" Failed to retrieve exchange rate data.")
        if "error_primary" in data:
            print(f"   - Primary Error: {data['error_primary']}")
        if "error_fallback" in data:
            print(f"   - Fallback Error: {data['error_fallback']}")
    print("=" * 50)


if __name__ == "__main__":
    print_formatted_summary()
