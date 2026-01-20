import datetime
import os
import shutil
import socket
import subprocess
import time
import json
import urllib.parse
from zoneinfo import ZoneInfo

import feedparser
import requests
from ddgs import DDGS

# --- WEB SEARCH --------------------------------------------------------

def _request_json(url, params=None, timeout=8):
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        return resp.json()
    except Exception as exc:
        return {"error": "request_failed", "detail": str(exc)}


def websearch_ddg(query):
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=5))
    except Exception:
        return [{"error": "ddg_failed"}]

def websearch_google(query):
    key = os.getenv("GOOGLE_PSE_KEY")
    cx = os.getenv("GOOGLE_PSE_ID")
    if not key or not cx:
        return [{"error": "google_pse_missing"}]
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": key, "cx": cx, "q": query}
    data = _request_json(url, params=params, timeout=8)
    if "error" in data:
        return [data]
    return data.get("items", [])

def web_search(query):
    return {"duckduckgo": websearch_ddg(query), "google": websearch_google(query)}

# --- SYSTEM ------------------------------------------------------------

_CPU_LAST = None


def _read_proc_stat():
    try:
        with open("/proc/stat", "r", encoding="utf-8") as f:
            line = f.readline()
        parts = [int(x) for x in line.strip().split()[1:]]
        total = sum(parts)
        idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
        return total, idle
    except Exception:
        return None


def _cpu_percent():
    global _CPU_LAST
    sample1 = _read_proc_stat()
    if not sample1:
        return None
    if _CPU_LAST is None:
        time.sleep(0.1)
        sample2 = _read_proc_stat()
        if not sample2:
            return None
        total1, idle1 = sample1
        total2, idle2 = sample2
        _CPU_LAST = sample2
    else:
        total1, idle1 = _CPU_LAST
        total2, idle2 = sample1
        _CPU_LAST = sample1
    total_delta = total2 - total1
    idle_delta = idle2 - idle1
    if total_delta <= 0:
        return None
    usage = (total_delta - idle_delta) / total_delta * 100.0
    return round(usage, 1)


def _mem_info():
    try:
        values = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                key, rest = line.split(":", 1)
                values[key.strip()] = int(rest.strip().split()[0])
        total = values.get("MemTotal", 0) / 1024
        avail = values.get("MemAvailable", 0) / 1024
        buffers = values.get("Buffers", 0) / 1024
        cached = values.get("Cached", 0) / 1024
        used = max(total - avail, 0)
        return {
            "total_mb": round(total, 1),
            "used_mb": round(used, 1),
            "available_mb": round(avail, 1),
            "buffered_mb": round(buffers + cached, 1),
        }
    except Exception:
        return None


def _disk_info():
    try:
        total, used, free = shutil.disk_usage("/")
        gb = 1024 ** 3
        return {
            "total_gb": round(total / gb, 1),
            "used_gb": round(used / gb, 1),
            "free_gb": round(free / gb, 1),
            "mount": "/",
        }
    except Exception:
        return None


def _ip_info():
    result = {"local_ip": None, "all_ips": []}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        result["local_ip"] = sock.getsockname()[0]
        sock.close()
    except Exception:
        pass
    try:
        output = subprocess.check_output(["ip", "-o", "addr"], text=True)
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[2] == "inet":
                ip = parts[3].split("/")[0]
                if ip != "127.0.0.1":
                    result["all_ips"].append(ip)
    except Exception:
        pass
    if result["local_ip"] and result["local_ip"] not in result["all_ips"]:
        result["all_ips"].append(result["local_ip"])
    return result


def system_info():
    cpu = _cpu_percent()
    mem = _mem_info()
    disk = _disk_info()
    ip = _ip_info()
    if cpu is None and mem is None and disk is None:
        return {"error": "system_info_unavailable"}
    return {"type": "system", "cpu_percent": cpu, "memory": mem, "disk": disk, "ip": ip}


def ping_host(host: str):
    if not host:
        return {"error": "missing_host"}
    try:
        output = subprocess.check_output(
            ["ping", "-c", "5", "-W", "2", host],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=10,
        )
    except Exception:
        return {"error": "ping_failed"}
    loss = None
    avg = None
    sent = None
    received = None
    for line in output.splitlines():
        if "packet loss" in line:
            try:
                parts = line.split(",")
                sent = int(parts[0].split()[0])
                received = int(parts[1].split()[0])
                loss = float(parts[2].split("%")[0].strip())
            except Exception:
                pass
        if "min/avg" in line:
            try:
                avg = float(line.split("=")[1].split("/")[1])
            except Exception:
                pass
    success = loss is not None and loss < 100.0
    return {
        "type": "ping",
        "host": host,
        "loss_percent": loss,
        "avg_ms": avg,
        "success": success,
        "sent": sent,
        "received": received,
        "raw": output,
    }

# --- IMAGES (COMFYUI) --------------------------------------------------

def _comfyui_workflow(prompt: str, model: str, width: int, height: int, steps: int, cfg: float, seed: int, negative: str):
    return {
        "3": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["3", 1]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["3", 1]}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["3", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "jarvis", "images": ["8", 0]}},
    }


def _comfyui_models(base_url: str):
    try:
        resp = requests.get(f"{base_url}/object_info", timeout=8)
        if not resp.ok:
            return []
        data = resp.json()
        loader = data.get("CheckpointLoaderSimple", {})
        inputs = loader.get("input", {}).get("required", {})
        models = inputs.get("ckpt_name", [[]])[0]
        return models if isinstance(models, list) else []
    except Exception:
        return []


def generate_image(prompt: str):
    prompt = (prompt or "").strip()
    if not prompt:
        return {"error": "missing_prompt"}
    base_url = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
    model = os.getenv("COMFYUI_MODEL", "dreamshaper.safetensors").strip() or "dreamshaper.safetensors"
    available = _comfyui_models(base_url)
    if available and model not in available:
        model = available[0]
    negative = os.getenv("COMFYUI_NEGATIVE", "low quality, worst quality, blurry").strip()
    width = int(os.getenv("COMFYUI_WIDTH", "512"))
    height = int(os.getenv("COMFYUI_HEIGHT", "512"))
    steps = int(os.getenv("COMFYUI_STEPS", "25"))
    cfg = float(os.getenv("COMFYUI_CFG", "7.0"))
    seed = int(time.time_ns()) % 1000000000
    workflow = _comfyui_workflow(prompt, model, width, height, steps, cfg, seed, negative)
    try:
        resp = requests.post(f"{base_url}/prompt", json={"prompt": workflow}, timeout=12)
    except Exception as exc:
        return {"error": "comfyui_unreachable", "detail": str(exc)}
    if not resp.ok:
        return {"error": "comfyui_failed", "detail": f"{resp.status_code}"}
    data = resp.json()
    prompt_id = data.get("prompt_id")
    if not prompt_id:
        return {"error": "comfyui_failed", "detail": "missing prompt_id"}
    deadline = time.time() + 120
    history = None
    while time.time() < deadline:
        try:
            h = requests.get(f"{base_url}/history/{prompt_id}", timeout=8)
            if h.ok:
                history = h.json()
                if history.get(prompt_id):
                    break
        except Exception:
            pass
        time.sleep(1)
    if not history or prompt_id not in history:
        return {"error": "comfyui_timeout"}
    outputs = history[prompt_id].get("outputs", {})
    image_info = None
    for node in outputs.values():
        for item in node.get("images", []):
            image_info = item
            break
        if image_info:
            break
    if not image_info:
        return {"error": "comfyui_failed", "detail": "no image output"}
    filename = image_info.get("filename")
    subfolder = image_info.get("subfolder", "")
    img_type = image_info.get("type", "output")
    params = {"filename": filename, "subfolder": subfolder, "type": img_type}
    try:
        img_resp = requests.get(f"{base_url}/view", params=params, timeout=12)
        if not img_resp.ok:
            return {"error": "comfyui_failed", "detail": "view failed"}
        content = img_resp.content
    except Exception as exc:
        return {"error": "comfyui_failed", "detail": str(exc)}
    return {"type": "image", "bytes": content, "content_type": "image/png", "filename": f"{prompt_id[:8]}.png"}


def list_processes(limit: int = 10):
    try:
        output = subprocess.check_output(["ps", "-eo", "pid,comm,%cpu,%mem", "--sort=-%cpu"], text=True)
    except Exception:
        return {"error": "ps_failed"}
    lines = output.strip().splitlines()[1:]
    items = []
    for line in lines[:limit]:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, comm, cpu, mem = parts
        items.append({"pid": int(pid), "name": comm, "cpu": float(cpu), "mem": float(mem)})
    return {"type": "processes", "items": items}


def find_process(query: str, limit: int = 5):
    if not query:
        return {"error": "missing_query"}
    try:
        output = subprocess.check_output(["ps", "-eo", "pid,comm,%cpu,%mem"], text=True)
    except Exception:
        return {"error": "ps_failed"}
    lines = output.strip().splitlines()[1:]
    items = []
    q = query.lower()
    for line in lines:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, comm, cpu, mem = parts
        if q in comm.lower():
            items.append({"pid": int(pid), "name": comm, "cpu": float(cpu), "mem": float(mem)})
            if len(items) >= limit:
                break
    return {"type": "processes", "items": items}


def kill_process(pid: int):
    if not pid:
        return {"error": "missing_pid"}
    try:
        subprocess.check_call(["kill", "-9", str(pid)])
        return {"type": "kill", "pid": pid, "ok": True}
    except Exception:
        return {"error": "kill_failed"}

def search_combined(query: str, max_items: int = 8) -> dict:
    items = []
    seen = set()
    ddg = websearch_ddg(query)
    if ddg and isinstance(ddg, list) and isinstance(ddg[0], dict) and ddg[0].get("error"):
        ddg = []
    for r in ddg:
        title = (r.get("title") or "").strip()
        url = (r.get("href") or "").strip()
        if not title or not url:
            continue
        key = (title.lower(), url)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "title": title,
                "snippet": _normalize_snippet(r.get("body")),
                "url": url,
                "source": "duckduckgo",
                "published_at": None,
            }
        )
        if len(items) >= max_items:
            break
    if len(items) < max_items:
        google = websearch_google(query)
        if google and isinstance(google, list) and isinstance(google[0], dict) and google[0].get("error"):
            google = []
        for r in google:
            title = (r.get("title") or "").strip()
            url = (r.get("link") or "").strip()
            if not title or not url:
                continue
            key = (title.lower(), url)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "title": title,
                    "snippet": _normalize_snippet(r.get("snippet")),
                    "url": url,
                    "source": "google",
                    "published_at": None,
                }
            )
            if len(items) >= max_items:
                break
    if not items:
        return {"error": "NO_RESULTS", "detail": "Ingen søgeresultater"}
    return {"type": "search", "query": query, "items": items[:max_items]}

# --- NEWS --------------------------------------------------------------

def _extract_news_query(text: str) -> str:
    lowered = text.lower()
    for marker in ["nyheder om", "nyheder angående", "nyheder vedrørende"]:
        if marker in lowered:
            return text[lowered.index(marker) + len(marker) :].strip()
    if lowered.strip() == "nyheder":
        return ""
    return text.strip()


def _normalize_snippet(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def _score_item(item: dict, tokens: list[str]) -> int:
    hay = f"{item.get('title','')} {item.get('snippet','')}".lower()
    return sum(1 for t in tokens if t and t in hay)


def _filter_items(items: list[dict], query: str) -> list[dict]:
    if not query:
        return items[:5]
    tokens = [t.lower() for t in query.split() if t]
    scored = [(i, _score_item(i, tokens)) for i in items]
    scored = [i for i in scored if i[1] > 0]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [i[0] for i in scored][:5]


def _to_iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        from datetime import datetime, timezone
        from email.utils import parsedate_to_datetime
        if "T" in value:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def _is_tech_query(query: str) -> bool:
    q = (query or "").lower()
    return any(k in q for k in ["tech", "teknologi", "ai", "kunstig intelligens", "machine learning"])


def news_api_search(q, category: str | None = None):
    key = os.getenv("NEWSAPI_KEY")
    if not key:
        return [{"error": "newsapi_key_missing"}]
    tech_hint = category == "technology" or _is_tech_query(q)
    if tech_hint:
        q = f"AI OR artificial intelligence OR machine learning OR OpenAI OR Google OR Nvidia {q}".strip()
    url = f"https://newsapi.org/v2/everything"
    params = {"q": q or "news", "apiKey": key, "pageSize": 10, "sortBy": "publishedAt"}
    data = _request_json(url, params=params, timeout=8)
    if "error" in data:
        return [data]
    items = []
    for a in data.get("articles", []):
        items.append(
            {
                "title": a.get("title") or "",
                "snippet": _normalize_snippet(a.get("description") or a.get("content")),
                "url": a.get("url") or "",
                "source": "newsapi",
                "published_at": _to_iso(a.get("publishedAt")),
            }
        )
    return items[:5]


def rss_news(feeds):
    feeds = [f.strip() for f in feeds if f.strip()]
    if not feeds:
        return [{"error": "rss_feeds_missing"}]
    out = []
    for f in feeds:
        d = feedparser.parse(f)
        for e in d.entries[:6]:
            out.append(
                {
                    "title": e.get("title") or "",
                    "snippet": _normalize_snippet(e.get("summary") or e.get("description")),
                    "url": e.get("link") or "",
                    "source": "rss",
                    "published_at": _to_iso(e.get("published") or e.get("updated")),
                }
            )
    return out


def _rss_feeds_for_query(query: str, category: str | None = None) -> list[str]:
    if category == "technology" or _is_tech_query(query):
        tech_feeds = os.getenv("RSS_TECH_FEEDS", "")
        feeds = tech_feeds.split(",") if tech_feeds else []
        if feeds:
            return feeds
    return os.getenv("RSS_FEEDS", "").split(",")


def web_search_news(query):
    allowed_env = os.getenv(
        "NEWS_WEB_ALLOWED_DOMAINS",
        "dr.dk,politiken.dk,bbc.co.uk,reuters.com,apnews.com,theguardian.com,nytimes.com,washingtonpost.com,aljazeera.com,bloomberg.com",
    )
    allowed = {d.strip().lower() for d in allowed_env.split(",") if d.strip()}
    blocked = {"instagram.com", "facebook.com", "wikipedia.org", "youtube.com", "tiktok.com"}

    def _domain_ok(url: str) -> bool:
        if not url:
            return False
        try:
            from urllib.parse import urlparse

            host = urlparse(url).netloc.lower()
        except Exception:
            return False
        if host.startswith("www."):
            host = host[4:]
        if any(host == b or host.endswith(f".{b}") for b in blocked):
            return False
        return any(host == a or host.endswith(f".{a}") for a in allowed)

    items = []
    for r in websearch_ddg(query):
        if isinstance(r, dict) and r.get("error"):
            continue
        if not _domain_ok(r.get("href") or ""):
            continue
        items.append(
            {
                "title": r.get("title") or "",
                "snippet": _normalize_snippet(r.get("body")),
                "url": r.get("href") or "",
                "source": "web",
                "published_at": None,
            }
        )
    for r in websearch_google(query):
        if isinstance(r, dict) and r.get("error"):
            continue
        if not _domain_ok(r.get("link") or ""):
            continue
        items.append(
            {
                "title": r.get("title") or "",
                "snippet": _normalize_snippet(r.get("snippet")),
                "url": r.get("link") or "",
                "source": "web",
                "published_at": None,
            }
        )
    return items


def read_article(url: str):
    if not url:
        return {"type": "article", "url": url, "title": "", "text": "", "error": "missing_url"}
    headers = {"User-Agent": "Mozilla/5.0 (JarvisBot/1.0)"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception:
        return {"type": "article", "url": url, "title": "", "text": "", "error": "fetch_failed"}
    html = resp.text or ""
    title = ""
    text = ""

    try:
        from readability import Document
        doc = Document(html)
        title = doc.short_title()
        html = doc.summary()
    except Exception:
        pass

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        if not title:
            t = soup.find("title")
            title = t.get_text(strip=True) if t else ""
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
    except Exception:
        text = html

    text = " ".join(text.split())
    if len(text) > 10000:
        text = text[:10000]
    return {"type": "article", "url": url, "title": title, "text": text, "error": None}


def news_combined(query, category: str | None = None):
    parsed = _extract_news_query(query)
    parsed = _extract_news_query(parsed) if parsed else parsed
    rss_items = rss_news(_rss_feeds_for_query(parsed or query, category))
    rss_items = [] if (rss_items and isinstance(rss_items[0], dict) and "error" in rss_items[0]) else rss_items
    rss_items = _filter_items(rss_items, parsed)

    api_items = news_api_search(parsed, category=category)
    api_items = [] if (api_items and isinstance(api_items[0], dict) and "error" in api_items[0]) else api_items
    api_items = _filter_items(api_items, parsed)

    web_items = web_search_news(parsed) if parsed else []
    web_items = _filter_items(web_items, parsed) if parsed else []

    combined = []
    seen = set()
    for src in (rss_items, api_items, web_items):
        for item in src:
            url = item.get("url") or ""
            if url in seen:
                continue
            seen.add(url)
            combined.append(item)
        if len(combined) >= 10:
            break

    def _ts(value: str | None) -> int:
        if not value:
            return 0
        try:
            from datetime import datetime
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
        except Exception:
            return 0

    combined.sort(key=lambda x: _ts(x.get("published_at")), reverse=True)
    combined = combined[:5]
    items = []
    for idx, item in enumerate(combined, start=1):
        items.append(
            {
                "id": f"n{idx}",
                "title": item.get("title") or "",
                "snippet": item.get("snippet") or "",
                "url": item.get("url") or "",
                "source": item.get("source") or "rss",
                "published_at": item.get("published_at"),
            }
        )
    return {"type": "news", "query": parsed, "items": items}


def news_search(query):
    return news_combined(query)

# --- WEATHER -----------------------------------------------------------

def _openweather_key():
    return os.getenv("OPENWEATHER_API_KEY") or os.getenv("OPENWEATHER_KEY")


def _geo_lookup(city):
    key = _openweather_key()
    if not key:
        return {"error": "MISSING_API_KEY"}
    default_country = os.getenv("WEATHER_DEFAULT_COUNTRY", "DK")
    query = " ".join(city.strip().strip("?!.,\"()").split())
    if "," not in query:
        query = f"{query},{default_country}"
    encoded = urllib.parse.quote_plus(query)
    url = f"https://api.openweathermap.org/geo/1.0/direct?q={encoded}&limit=5&appid={key}"
    data = _request_json(url, timeout=8)
    if isinstance(data, dict) and data.get("error"):
        return {"error": "REQUEST_FAILED", "detail": "geocoding"}
    if not data:
        return {"error": "CITY_NOT_FOUND", "detail": f"No matches for '{query}'"}
    best = None
    for item in data:
        if item.get("country") == default_country:
            best = item
            break
    if best is None:
        best = data[0]
    return {"lat": best.get("lat"), "lon": best.get("lon"), "name": best.get("name"), "country": best.get("country")}


def weather_now(city):
    key = _openweather_key()
    if not key:
        return {"error": "MISSING_API_KEY"}
    geo = _geo_lookup(city)
    if geo.get("error"):
        return geo
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"lat": geo["lat"], "lon": geo["lon"], "appid": key, "units": "metric", "lang": "da"}
    return _request_json(url, params=params, timeout=8)


def weather_forecast(city):
    key = _openweather_key()
    if not key:
        return {"error": "MISSING_API_KEY"}
    geo = _geo_lookup(city)
    if geo.get("error"):
        return geo
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"lat": geo["lat"], "lon": geo["lon"], "appid": key, "units": "metric", "lang": "da"}
    return _request_json(url, params=params, timeout=8)


def format_weather_today(now_json, tz="Europe/Copenhagen") -> str | None:
    if not isinstance(now_json, dict) or now_json.get("error"):
        return None
    main = now_json.get("main", {})
    wind = now_json.get("wind", {})
    weather_list = now_json.get("weather") or []
    desc = weather_list[0].get("description") if weather_list else None
    temp = main.get("temp")
    feels = main.get("feels_like")
    speed = wind.get("speed")
    if temp is None or feels is None or speed is None or not desc:
        return None
    return f"{temp:.0f}°C (føles {feels:.0f}°C), {desc}, vind {speed:.1f} m/s."


def _forecast_day_groups(forecast_json, tz):
    if not isinstance(forecast_json, dict) or forecast_json.get("error"):
        return {}
    items = forecast_json.get("list") or []
    if not items:
        return {}
    from datetime import datetime
    from zoneinfo import ZoneInfo

    zone = ZoneInfo(tz)
    by_date = {}
    for item in items:
        if "dt" in item:
            dt = datetime.fromtimestamp(item["dt"], tz=zone)
        else:
            dt_txt = item.get("dt_txt")
            if not dt_txt:
                continue
            try:
                dt = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S").replace(tzinfo=zone)
            except Exception:
                continue
        date_key = dt.date().isoformat()
        by_date.setdefault(date_key, []).append(item)
    return by_date


def _summarize_day(day_items):
    from collections import Counter

    temps = [i.get("main", {}).get("temp") for i in day_items]
    temps = [t for t in temps if t is not None]
    winds = [i.get("wind", {}).get("speed") for i in day_items]
    winds = [w for w in winds if w is not None]
    descs = []
    for i in day_items:
        wl = i.get("weather") or []
        if wl and wl[0].get("description"):
            descs.append(wl[0]["description"])
    if not temps or not descs:
        return None
    min_temp = min(temps)
    max_temp = max(temps)
    avg_temp = sum(temps) / len(temps)
    max_wind = max(winds) if winds else None
    desc = Counter(descs).most_common(1)[0][0]
    return {
        "avg": avg_temp,
        "min": min_temp,
        "max": max_temp,
        "desc": desc,
        "max_wind": max_wind,
    }


def _day_name(dt):
    names = ["Man", "Tir", "Ons", "Tor", "Fre", "Lør", "Søn"]
    return names[dt.weekday()]


def format_weather_tomorrow(forecast_json, tz="Europe/Copenhagen") -> str | None:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    by_date = _forecast_day_groups(forecast_json, tz)
    if not by_date:
        return None
    zone = ZoneInfo(tz)
    tomorrow = (datetime.now(zone).date() + timedelta(days=1)).isoformat()
    if tomorrow not in by_date:
        return None
    info = _summarize_day(by_date[tomorrow])
    if not info:
        return None
    wind_text = f", vind op til {info['max_wind']:.1f} m/s" if info["max_wind"] is not None else ""
    return f"{info['min']:.0f}–{info['max']:.0f}°C, {info['desc']}{wind_text}."


def format_weather_5days(forecast_json, tz="Europe/Copenhagen") -> str | None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    by_date = _forecast_day_groups(forecast_json, tz)
    if not by_date:
        return None
    zone = ZoneInfo(tz)
    today = datetime.now(zone).date()
    lines = []
    for date_key in sorted(by_date.keys()):
        date_obj = datetime.fromisoformat(date_key).date()
        if date_obj < today:
            continue
        info = _summarize_day(by_date[date_key])
        if not info:
            continue
        day_label = _day_name(datetime.fromisoformat(date_key))
        lines.append(
            f"{day_label} {date_obj.day}/{date_obj.month}: {info['min']:.0f}–{info['max']:.0f}°C, {info['desc']}"
        )
        if len(lines) >= 5:
            break
    if not lines:
        return None
    return "\n".join(lines)

# --- CURRENCY ----------------------------------------------------------

def currency_convert(frm, to, amount=1):
    url = f"https://api.exchangerate.host/convert?from={frm}&to={to}&amount={amount}"
    return _request_json(url, timeout=8)

# --- TIME --------------------------------------------------------------

def time_now():
    tz = os.getenv("TIMEZONE", "Europe/Copenhagen")
    return datetime.datetime.now(ZoneInfo(tz)).isoformat()
