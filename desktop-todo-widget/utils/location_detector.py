"""Location detector: detect current city via IP geolocation.

Uses free IP-API.com service (no API key required, 45 requests/minute limit).
Falls back gracefully if the service is unavailable.
"""
import json
import urllib.request
import urllib.error


def detect_city() -> str:
    """Detect current city via IP geolocation.
    Returns city name (e.g. '合肥', '广州') or empty string on failure.
    """
    try:
        req = urllib.request.Request(
            "http://ip-api.com/json/?lang=zh-CN",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") == "success":
            city = data.get("city", "")
            return city.strip()
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        pass
    return ""


def detect_city_safe() -> str:
    """Safe wrapper that never raises exceptions."""
    try:
        return detect_city()
    except Exception:
        return ""
