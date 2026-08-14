"""Weather checker: fetch weather from wttr.in, analyze with Claude API.

Two-tier design for continuous app:
  - fetch_temps()       -> quick wttr.in call, NO AI, for live display
  - analyze_alerts()    -> wttr.in + Claude AI, once per day, for notifications

City format:
  - weather_home_city: fixed home city (default "合肥")
  - weather_last_city: previously detected non-home city
  - Dynamic ordering: detected city first, home city second
"""
import json
from datetime import datetime

import requests
from anthropic import Anthropic

# API config loaded from settings (not hardcoded)


def _list_cities(settings: dict) -> list:
    """Build ordered city list.

    Model: two cities — home (first by default) + a second city.
      - If weather_manual_city is set → it wins over IP detection
      - Otherwise → detect current city via IP (fallback: last_city)
      - weather_swap_order=True → reverse order
    """
    home = settings.get("weather_home_city", "合肥")
    second = settings.get("weather_manual_city", "").strip()
    swap = settings.get("weather_swap_order", False)

    if second:
        # Manual input has highest priority — overrides auto detection
        if second != home:
            settings["weather_last_city"] = second
    else:
        # Auto-detect via IP
        from utils.location_detector import detect_city_safe
        detected = detect_city_safe()
        if detected:
            settings["weather_last_city"] = detected
            second = detected
        else:
            second = settings.get("weather_last_city", "宿州")

    # Avoid duplicate cities
    if second == home:
        second = settings.get("weather_last_city", "宿州")
        if second == home:
            second = "宿州"

    result = [home, second]
    if swap:
        result.reverse()
    return result


def _names_map(settings: dict, cities: list) -> dict:
    """Build display-name map from settings."""
    names = settings.get("weather_names", {})
    if not names:
        names = {c: c for c in cities}
    return names


def _fetch_one(city: str) -> dict:
    """Fetch weather for a single city from wttr.in."""
    url = f"https://wttr.in/{city}?format=j1&lang=zh"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        cur = data.get("current_condition", [{}])[0]
        desc = cur.get("weatherDesc", [{}])[0].get("value", "").strip()
        wind_kph = cur.get("windspeedKmph", "0")
        return {
            "temp": cur.get("temp_C", "?"),
            "feels": cur.get("FeelsLikeC", "?"),
            "desc": desc,
            "wind": f"{wind_kph}km/h",
            "wind_dir": cur.get("winddir16Point", ""),
            "humidity": f"{cur.get('humidity', '?')}%",
            "vis": f"{cur.get('visibility', '?')}km",
            "pressure": f"{cur.get('pressure', '?')}hPa",
        }
    except Exception:
        return {"temp": "?", "feels": "?", "desc": "获取失败",
                "wind": "", "wind_dir": "", "humidity": "",
                "vis": "", "pressure": ""}


def fetch_temps(settings: dict) -> list:
    """Quick city-temperature fetch, NO AI. Returns list of {name, temp, feels, desc}."""
    from config.settings_manager import save_settings

    cities = _list_cities(settings)
    names = _names_map(settings, cities)

    results = []
    for city in cities:
        name = names.get(city, city)
        data = _fetch_one(city)
        results.append({"name": name, **data})
    # Save settings if _list_cities modified weather_last_city
    save_settings(settings)
    return results


def analyze_alerts(settings: dict) -> dict:
    """Full weather check + AI analysis. Returns alerts + temp info."""
    cities = _list_cities(settings)
    names = _names_map(settings, cities)

    results = []
    alerts = []

    for city in cities:
        name = names.get(city, city)
        try:
            raw = fetch_weather(city)
            snap = get_temp_snapshot(raw)
            summary = extract_summary(raw, name)
            result = analyze_weather(summary, name, settings)
            if result.get("needs_alert"):
                alerts.append({**result, "city": name})
            results.append({"name": name, "temp": snap["temp"], "desc": snap["desc"]})
        except Exception as e:
            results.append({"name": name, "temp": "?", "desc": str(e)})

    temp_line = " | ".join(f"{r['name']} {r['temp']}°C" for r in results)
    return {"results": results, "alerts": alerts, "temp_line": temp_line}


def fetch_weather(city: str) -> dict:
    url = f"https://wttr.in/{city}?format=j1&lang=zh"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_temp_snapshot(data: dict) -> dict:
    cur = data.get("current_condition", [{}])[0]
    return {
        "temp": cur.get("temp_C", "?"),
        "feels": cur.get("FeelsLikeC", "?"),
        "desc": cur.get("weatherDesc", [{}])[0].get("value", "").strip(),
    }


def extract_summary(data: dict, name: str) -> str:
    cur = data.get("current_condition", [{}])[0]
    forecast = data.get("weather", [])
    desc = cur.get("weatherDesc", [{}])[0].get("value", "").strip()
    temp = cur.get("temp_C", "?")
    feels = cur.get("FeelsLikeC", "?")
    humidity = cur.get("humidity", "?")
    wind = cur.get("windspeedKmph", "?")
    vis = cur.get("visibility", "?")

    lines = [
        f"📍 城市：{name}",
        f"🌤 天气：{desc}",
        f"🌡 气温：{temp}°C（体感 {feels}°C）",
        f"💧 湿度：{humidity}%",
        f"🌬 风速：{wind} km/h",
        f"👁 能见度：{vis} km",
        "",
        "📅 未来天气预报：",
    ]

    for day in forecast[:3]:
        date, avg_temp = day.get("date", "?"), day.get("avgtempC", "?")
        hourly = day.get("hourly", [{}])
        day_hours = [h for h in hourly if 6 <= int(h.get("time", "0")) // 100 <= 18] or hourly[:4]
        max_rain = max(int(h.get("chanceofrain", "0")) for h in day_hours)
        max_snow = max(int(h.get("chancesnow", "0")) for h in day_hours)
        max_fog = max(int(h.get("chanceoffog", "0")) for h in day_hours)
        max_wind = max(int(h.get("windspeedKmph", "0")) for h in day_hours)
        wdesc = day_hours[len(day_hours) // 2].get("weatherDesc", [{}])[0].get("value", "").strip()
        hi = max(int(h.get("FeelsLikeC", "0")) for h in hourly)

        warns = []
        if max_rain >= 60: warns.append(f"降雨{max_rain}%")
        if max_snow >= 40: warns.append(f"降雪{max_snow}%")
        if max_fog >= 50: warns.append(f"大雾{max_fog}%")
        if max_wind >= 60: warns.append(f"大风{max_wind}km/h")
        suffix = f" ⚠️{'、'.join(warns)}" if warns else ""
        lines.append(f"  {date} {wdesc} {avg_temp}°C（最高体感{hi}°C）{suffix}")

    return "\n".join(lines)


def analyze_weather(summary: str, city: str, settings: dict = None) -> dict:
    """AI analysis of weather summary. Reads API config from settings."""
    if settings is None:
        settings = {}
    api_key = settings.get("weather_api_key", "")
    base_url = settings.get("weather_api_base_url", "https://api.deepseek.com/anthropic")
    max_tokens = settings.get("weather_api_max_tokens", 500)

    if not api_key:
        return {"needs_alert": False, "severity": "low",
                "title": "未配置", "body": "请在设置中配置天气 API Key",
                "reasons": ["API Key 未设置"]}

    client = Anthropic(api_key=api_key, base_url=base_url)
    sys_prompt = """你是天气预报助手。根据天气数据判断是否需要提醒用户注意。

返回格式（严格 JSON，不要 markdown 代码块）：
{
  "needs_alert": true/false,
  "severity": "low"/"medium"/"high",
  "title": "通知标题（10字以内）",
  "body": "通知正文（30字以内）",
  "reasons": ["原因1", "原因2"]
}

判断标准：
- 下雨概率 >= 60% → needs_alert=true
- 下雪概率 >= 40% → needs_alert=true
- 大雾概率 >= 50% → needs_alert=true
- 大风 >= 50km/h → needs_alert=true
- 体感温度 >= 38°C → needs_alert=true
- 体感温度 <= -10°C → needs_alert=true
- 晴天/多云/阴天 → needs_alert=false
- severity: 下雨/下雪/极端温度=high, 大风/大雾=medium, 轻微不适=low
"""
    msg = client.messages.create(
        model="deepseek-v4-flash",
        max_tokens=max_tokens,
        system=sys_prompt,
        messages=[{"role": "user", "content": f"分析{city}的天气：\n\n{summary}"}],
    )
    text = ""
    for block in msg.content:
        if hasattr(block, "text"):
            text = block.text
            break
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)
