"""
Test script untuk cek model Gemini mana yang tersedia dengan API key kamu.
Jalankan: python test_models.py YOUR_API_KEY
"""

import sys
import requests

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

MODELS_TO_TEST = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash",
]

def test_model(model: str, api_key: str) -> None:
    """Test satu model dengan prompt sederhana (pattern sama dgn CV scoring)."""
    url = GEMINI_API_URL.format(model=model)
    payload = {
        "contents": [{"parts": [{"text": "Jawab dalam 1 kata: ibukota Indonesia?"}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 256,
            "responseMimeType": "application/json",
        },
    }
    try:
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            params={"key": api_key},
            json=payload,
            timeout=90,
        )
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    text = parts[0].get("text", "")
                    print(f"  ✅ {model}: OK — {text.strip()[:60]}")
                    return
            print(f"  ⚠️ {model}: 200 but no content")
        else:
            detail = resp.json().get("error", {}).get("message", resp.text[:100])
            print(f"  ❌ {model}: HTTP {resp.status_code} — {detail[:80]}")
    except Exception as e:
        print(f"  ❌ {model}: {type(e).__name__}: {e}")


def list_available_models(api_key: str) -> None:
    """List semua model yang tersedia."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            gemini_models = [m["name"] for m in models if "gemini" in m.get("name", "").lower()]
            print(f"\nModel Gemini tersedia ({len(gemini_models)}):")
            for m in sorted(gemini_models):
                print(f"  - {m}")
        else:
            print(f"Gagal list models: HTTP {resp.status_code}")
    except Exception as e:
        print(f"Gagal list models: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_models.py YOUR_GEMINI_API_KEY")
        sys.exit(1)

    api_key = sys.argv[1]
    print("Testing model availability...\n")

    for model in MODELS_TO_TEST:
        test_model(model, api_key)

    list_available_models(api_key)
    print("\nSelesai!")
