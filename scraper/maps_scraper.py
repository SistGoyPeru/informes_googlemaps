import base64
import csv
import hashlib
import json
import re
import struct
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
FEATURE_ID_RE = re.compile(r"!1s(0x[0-9a-f]{1,16}):(0x[0-9a-f]{1,16})", re.IGNORECASE)
FTID_RE = re.compile(r"[?&]ftid=(0x[0-9a-f]{1,16}):(0x[0-9a-f]{1,16})", re.IGNORECASE)
DEFAULT_URL = "https://www.google.com/maps/place/BURGER+NUKENZI/@41.5636477,2.0197395,19.25z/data=!4m6!3m5!1s0x12a493006f1f1801:0xd7205ae52356465b!8m2!3d41.5639303!4d2.0200143!16s%2Fg%2F11yqxd4y9s?hl=es"
CARD_SELECTORS = ("div.jftiEf[data-review-id]",)
AUTHOR_SELECTORS = ("[class*='TSUbDb']", "[class*='d4r55']")
DATE_SELECTORS = ("[class*='rsqaWe']", "[class*='Ing6Fd']")
TEXT_SELECTORS = (".wiI7pd",)
RESPONSE_SELECTORS = ("div.CDe7pd .wiI7pd",)
REVIEW_FIELDS = ["review_id", "author", "rating", "date", "text", "owner_response"]
STEALTH_ARGS = ["--disable-blink-features=AutomationControlled", "--disable-infobars"]
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"


def place_id_from_maps_url(url):
    match = FEATURE_ID_RE.search(url or "") or FTID_RE.search(url or "")
    if not match:
        return ""
    high = int(match.group(1), 16)
    low = int(match.group(2), 16)
    payload = b"\x0a\x12\x09" + struct.pack("<Q", high) + b"\x11" + struct.pack("<Q", low)
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def fallback_key(url):
    return "url-" + hashlib.sha1((url or "").encode("utf-8")).hexdigest()[:20]


def _clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _first_text(root, selectors):
    for selector in selectors:
        locator = root.locator(selector)
        if locator.count():
            text = _clean(locator.first.inner_text())
            if text:
                return text
    return ""


def _parse_rating(value):
    match = re.search(r"(\d+(?:[.,]\d+)?)", value or "")
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _normalize_date(value):
    text = _clean(value).lower()
    if not text:
        return ""
    match = re.search(r"hace\s+(\d+|un|una)\s*(d[ií]a|semana|mes|a[nñ]o|hora)", text)
    if not match:
        return value
    token = match.group(1)
    amount = 1 if token in ("un", "una") else int(token)
    unit = match.group(2)
    days = {
        "día": amount,
        "dia": amount,
        "semana": amount * 7,
        "mes": amount * 30,
        "año": amount * 365,
        "ano": amount * 365,
        "hora": amount / 24,
    }[unit]
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")


def _handle_consent(page):
    if "consent.google" in page.url:
        page.get_by_role("button", name="Aceptar todo").first.click()
        page.wait_for_timeout(4000)


def _login_required(page):
    if "accounts.google.com" in page.url or "consent.google" in page.url:
        return True
    body = page.locator("body").inner_text()
    return "Inicia sesión para disfrutar" in body or "vista limitada" in body or "Iniciar sesión" in body


def _context_options(headless):
    return {
        "channel": "chrome",
        "headless": headless,
        "locale": "es-ES",
        "viewport": {"width": 1400, "height": 1000},
        "ignore_default_args": ["--enable-automation"],
        "args": STEALTH_ARGS,
        "user_agent": USER_AGENT,
    }


def _max_photo_index(page):
    labels = page.evaluate("() => [...document.querySelectorAll('[aria-label^=\"Foto \"]')].map(e => e.getAttribute('aria-label'))")
    values = []
    for label in labels or []:
        match = re.match(r"Foto\s+(\d+)", label or "")
        if match:
            values.append(int(match.group(1)))
    return max(values) if values else 0


def _count_photos(page, iterations=30):
    previous = -1
    for _ in range(iterations):
        current = _max_photo_index(page)
        if current and current == previous:
            break
        previous = current
        page.evaluate(
            "() => { const es=[...document.querySelectorAll('*')].filter(e => e.scrollHeight>e.clientHeight+50 && ['auto','scroll'].includes(getComputedStyle(e).overflowY)); es.forEach(e => e.scrollTop=e.scrollHeight); window.scrollBy(0,2000); }"
        )
        page.wait_for_timeout(1200)
    return _max_photo_index(page)


def _rating_counts(page):
    counts = {}
    for row in page.locator("[aria-label*='estrella'][aria-label*='reseñas']").all():
        label = _clean(row.get_attribute("aria-label"))
        match = re.match(r"(\d+)\s+estrellas?,\s*(\d+)\s+reseñas", label)
        if match:
            counts[int(match.group(1))] = int(match.group(2))
    return {str(key): counts.get(key, 0) for key in range(1, 6)}


def scrape_basic(url=DEFAULT_URL, headless=True):
    profile = DATA_DIR / "chrome_profile"
    profile.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(str(profile), **_context_options(headless))
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        _handle_consent(page)
        page.wait_for_selector("[role='img'][aria-label*='estrella']", timeout=30000)
        page.wait_for_timeout(7000)

        name = page.title().replace(" - Google Maps", "").strip()
        rating_label = page.locator("[role='img'][aria-label*='estrella']").first.get_attribute("aria-label")
        address = ""
        phone = ""
        hours = ""
        category = ""

        address_locator = page.locator("button[aria-label^='Dirección:']")
        if address_locator.count():
            address = _clean(address_locator.first.get_attribute("aria-label")).removeprefix("Dirección:").strip()
        phone_locator = page.locator("button[aria-label^='Teléfono:']")
        if phone_locator.count():
            phone = _clean(phone_locator.first.get_attribute("aria-label")).removeprefix("Teléfono:").strip()
        hours_locator = page.locator("button[aria-label*='Copiar el horario']")
        if hours_locator.count():
            hours = _clean(hours_locator.first.get_attribute("aria-label")).replace(", Copiar el horario", "")

        for button in page.locator("button").all():
            text = _clean(button.inner_text())
            if text in {"Hamburguesería", "Restaurante", "Cafetería", "Bar", "Pizzería", "Comida rápida"}:
                category = text
                break

        photos = []
        for image in page.locator("img[src*='lh3.googleusercontent.com']").all():
            src = image.get_attribute("src") or ""
            if src and src not in photos:
                photos.append(src)

        body_text = page.locator("body").inner_text()
        login_required = _login_required(page)
        rating_counts = _rating_counts(page)
        review_total = sum(rating_counts.values())
        if not review_total:
            total_match = re.search(r"(\d+)\s+reseñas", body_text)
            review_total = int(total_match.group(1)) if total_match else 0

        photo_total = 0
        owner_photos = 0
        try:
            see_photos = page.get_by_role("button", name="Ver fotos")
            if see_photos.count():
                see_photos.first.click()
                page.wait_for_timeout(5000)
                photo_total = _count_photos(page)
                owner_tab = page.locator("[aria-label='Del propietario']")
                if owner_tab.count():
                    owner_tab.first.click()
                    page.wait_for_timeout(4000)
                    owner_photos = _count_photos(page)
        except PlaywrightError:
            pass
        context.close()

    place_id = place_id_from_maps_url(url) or fallback_key(url)

    return {
        "name": name,
        "place_id": place_id,
        "category": category,
        "rating": _parse_rating(rating_label),
        "address": address,
        "phone": phone,
        "hours": hours,
        "login_required": login_required,
        "review_total": review_total,
        "rating_counts": rating_counts,
        "photo_total": photo_total,
        "owner_photos": owner_photos,
        "customer_photos": max(photo_total - owner_photos, 0),
        "source_url": url,
        "photos": photos,
    }


def _parse_review_card(card):
    lines = [_clean(line) for line in card.inner_text().splitlines() if _clean(line)]
    rating_label = ""
    rating_locator = card.locator("[role='img'][aria-label*='estrella']")
    if rating_locator.count():
        rating_label = rating_locator.first.get_attribute("aria-label") or ""
    rating = _parse_rating(rating_label)
    if rating is None or not 1 <= rating <= 5:
        rating = None

    texts = [_clean(value) for value in card.locator(".wiI7pd").all_inner_texts()]
    texts = [value for value in texts if value]
    response = _first_text(card, RESPONSE_SELECTORS)
    if response and texts and response == texts[-1] and len(texts) > 1:
        texts = texts[:-1]

    return {
        "author": _first_text(card, AUTHOR_SELECTORS) or (lines[0] if lines else ""),
        "rating": rating,
        "date": _normalize_date(_first_text(card, DATE_SELECTORS)),
        "text": texts[0] if texts else "",
        "owner_response": response,
    }


def scrape_reviews(url=DEFAULT_URL, user_data_dir=None, limit=100, wait_seconds=180, headless=False):
    profile = Path(user_data_dir) if user_data_dir else DATA_DIR / "chrome_profile"
    profile.mkdir(parents=True, exist_ok=True)
    collected = {}

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(str(profile), **_context_options(headless))
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        _handle_consent(page)
        page.wait_for_timeout(5000)

        try:
            if _login_required(page):
                print("Inicia sesión en la ventana de Chrome que se acaba de abrir.", flush=True)
                login_url = "https://accounts.google.com/ServiceLogin?hl=es&continue=" + quote(url, safe="")
                page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
                deadline = time.monotonic() + wait_seconds
                while time.monotonic() < deadline:
                    page.wait_for_timeout(2000)
                    try:
                        if not _login_required(page):
                            break
                    except PlaywrightError:
                        break
                else:
                    raise TimeoutError("No se detectó el inicio de sesión en Google Maps")
                if "google.com/maps" not in page.url:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(5000)

            rating = page.locator("[role='img'][aria-label*='estrella']").first
            if rating.count():
                rating.click()
                page.wait_for_timeout(4000)

            more_reviews = page.locator("button[jsaction*='reviewChart.moreReviews']")
            if more_reviews.count():
                more_reviews.first.click()
                page.wait_for_timeout(5000)

            seen_ids = set()
            stale = 0
            for _ in range(140):
                ids = page.evaluate(
                    "() => [...document.querySelectorAll('div.jftiEf[data-review-id]')].map(e => e.getAttribute('data-review-id'))"
                ) or []
                fresh = [index for index, review_id in enumerate(ids) if review_id and review_id not in seen_ids]
                for index in fresh:
                    review_id = ids[index]
                    seen_ids.add(review_id)
                    row = _parse_review_card(page.locator("div.jftiEf[data-review-id]").nth(index))
                    if row["text"] or row["author"] or row["rating"]:
                        row["review_id"] = review_id
                        collected[review_id] = row
                if len(collected) >= limit:
                    break
                stale = 0 if fresh else stale + 1
                if stale >= 8:
                    break
                page.evaluate(
                    "() => { const es=[...document.querySelectorAll('*')].filter(e => e.scrollHeight>e.clientHeight+50 && ['auto','scroll'].includes(getComputedStyle(e).overflowY)); es.forEach(e => e.scrollTop=e.scrollHeight); window.scrollBy(0,2000); }"
                )
                page.wait_for_timeout(700)
        except PlaywrightError as error:
            print(f"Chrome se cerró; se guardan {len(collected)} reseñas parciales: {error}", flush=True)
        finally:
            try:
                context.close()
            except PlaywrightError:
                pass

    return list(collected.values())[:limit]


def save_basic(data, path=None):
    target = Path(path) if path else DATA_DIR / "place.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def save_reviews(rows, path=None):
    target = Path(path) if path else DATA_DIR / "reviews.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    fields = REVIEW_FIELDS
    with target.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return target


def load_reviews(path=None):
    target = Path(path) if path else DATA_DIR / "reviews.csv"
    if not target.exists():
        return []
    with target.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def export_all(path=None):
    place_path = DATA_DIR / "place.json"
    place = json.loads(place_path.read_text(encoding="utf-8")) if place_path.exists() else {}
    reviews = load_reviews()
    ratings = place.get("rating_counts") or {}
    summary = {
        "name": place.get("name", ""),
        "place_id": place.get("place_id", ""),
        "rating": place.get("rating"),
        "review_total": place.get("review_total", 0),
        "reviews_exported": len(reviews),
        "rating_counts": ratings,
        "photo_total": place.get("photo_total", 0),
        "owner_photos": place.get("owner_photos", 0),
        "customer_photos": place.get("customer_photos", 0),
        "address": place.get("address", ""),
        "phone": place.get("phone", ""),
        "hours": place.get("hours", ""),
    }
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_url": place.get("source_url", DEFAULT_URL),
        "summary": summary,
        "place": place,
        "reviews": reviews,
    }
    target = Path(path) if path else DATA_DIR / "dashboard.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_path = DATA_DIR / "resumen.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["campo", "valor"])
        for key, value in summary.items():
            writer.writerow([key, json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value])
    return target, summary_path


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "basic"
    if command == "basic":
        data = scrape_basic()
        print(str(save_basic(data)))
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif command in ("reviews", "reviews-headless"):
        values = [value for value in sys.argv[2:] if value.isdigit()]
        limit = int(values[0]) if values else 100
        rows = scrape_reviews(limit=limit, headless=command == "reviews-headless")
        merged = {}
        for row in load_reviews() + rows:
            key = row.get("review_id") or (row.get("author"), row.get("text"), row.get("date"))
            merged[key] = row
        rows = list(merged.values())[:limit]
        print(str(save_reviews(rows)))
        print(f"{len(rows)} reseñas guardadas")
    elif command == "export":
        targets = export_all()
        for target in targets:
            print(str(target))
    else:
        raise SystemExit("Uso: python -m scraper.maps_scraper basic|reviews|reviews-headless|export [limit]")


if __name__ == "__main__":
    main()
