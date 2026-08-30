"""
main.py -- The Polite Scraper (Books to Scrape)

Fetches the first 3 catalogue pages, discovers all 60 book URLs, visits
every book page, extracts raw fields, cleans/validates them, and writes:

    output/books.json        -- 60 clean, validated records
    output/errors.json       -- any records that failed validation
    output/run-report.json   -- honest numbers about what happened

Run it with:
    python main.py

Run it TWICE to see the checkpoint behavior:
    1st run  -> prints FETCH for every page, creates cache/ files
    2nd run  -> prints CACHE HIT for every page (reads the saved copies)
"""

import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ValidationError

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CATALOGUE_URL = "https://books.toscrape.com/catalogue/page-1.html"
USER_AGENT = "FlyRankInternshipA9/1.0 (+https://github.com/ayeshaijaz02/task-api)"
TIMEOUT = 10
DELAY = 0.6  # seconds between real (non-cached) requests, per the "be polite" rule
CACHE_DIR = "cache"
OUTPUT_DIR = "output"

RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

# To test Stage 5 (one bad page must not kill the run), set this to True.
# It adds one fake book URL that will fail on purpose, then set it back to
# False once you've confirmed the run still finishes.
INJECT_FAKE_URL_FOR_TESTING = False

stats = {
    "start_time": None,
    "pages_fetched": 0,
    "cache_hits": 0,
    "valid_records": 0,
    "invalid_records": 0,
    "failed_pages": 0,
    "failed_urls": [],
}


# ---------------------------------------------------------------------------
# Stage 1: Fetch once, cache once
# ---------------------------------------------------------------------------
def cache_path(name: str) -> str:
    return os.path.join(CACHE_DIR, name)


def fetch(url: str, cache_name: str, allow_retry: bool = True) -> Optional[str]:
    """
    Fetch a URL politely: honest user-agent, timeout, status check, delay.
    Uses a saved copy in cache/ if one already exists, so re-running the
    script during development does not hit the real site again.
    Returns the HTML text, or None if the page could not be fetched.
    """
    path = cache_path(cache_name)
    if os.path.exists(path):
        stats["cache_hits"] += 1
        print(f"CACHE HIT  {url}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        print(f"FAIL       {url}  ({e})")
        if allow_retry:
            time.sleep(1)
            return fetch(url, cache_name, allow_retry=False)
        stats["failed_pages"] += 1
        stats["failed_urls"].append(url)
        return None

    # Only 200 means "here is your page"
    if resp.status_code == 200:
        stats["pages_fetched"] += 1
        print(f"FETCH      {url}  size={len(resp.text)}")
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(resp.text)
        time.sleep(DELAY)
        return resp.text

    # Never retry a 404 (doesn't exist) or 403 (site said no)
    if resp.status_code in (404, 403):
        print(f"SKIP {resp.status_code}    {url}")
        stats["failed_pages"] += 1
        stats["failed_urls"].append(url)
        return None

    # Retry once on a server error (5xx)
    if resp.status_code >= 500 and allow_retry:
        print(f"RETRY {resp.status_code}   {url}")
        time.sleep(1)
        return fetch(url, cache_name, allow_retry=False)

    print(f"FAIL {resp.status_code}     {url}")
    stats["failed_pages"] += 1
    stats["failed_urls"].append(url)
    return None


# ---------------------------------------------------------------------------
# Stage 2: Find all three catalogue pages, collect every book link
# ---------------------------------------------------------------------------
def discover_book_urls() -> list[str]:
    urls = []
    page_url = CATALOGUE_URL
    page_num = 1

    while page_url and page_num <= 3:
        html = fetch(page_url, f"catalogue-page-{page_num}.html")
        if html is None:
            break
        soup = BeautifulSoup(html, "html.parser")

        for article in soup.select("article.product_pod"):
            link = article.select_one("h3 a")
            if link and link.get("href"):
                urls.append(urljoin(page_url, link["href"]))

        next_link = soup.select_one("li.next a")
        if next_link and next_link.get("href") and page_num < 3:
            page_url = urljoin(page_url, next_link["href"])
            page_num += 1
        else:
            page_url = None

    unique_urls = list(dict.fromkeys(urls))  # de-dupe, keep order
    print(
        f"\ncatalogue_pages={min(page_num, 3)} "
        f"discovered={len(urls)} unique_urls={len(unique_urls)}\n"
    )
    return unique_urls


# ---------------------------------------------------------------------------
# Stage 3: Extract the raw record from one book page
# ---------------------------------------------------------------------------
def extract_book(url: str, index: int) -> Optional[dict]:
    html = fetch(url, f"book-{index}.html")
    if html is None:
        return None

    soup = BeautifulSoup(html, "html.parser")
    product = soup.select_one("div.product_main")

    title = product.select_one("h1").get_text(strip=True) if product else None

    price_el = soup.select_one("p.price_color")
    price_text = price_el.get_text(strip=True) if price_el else None

    avail_el = soup.select_one("p.availability")
    availability_text = avail_el.get_text(strip=True) if avail_el else None

    rating_text = None
    rating_el = soup.select_one("p.star-rating")
    if rating_el:
        for cls in rating_el.get("class", []):
            if cls in RATING_WORDS:
                rating_text = cls
                break

    # Some books have no description -- store null, never invent text
    description = None
    desc_heading = soup.find("div", id="product_description")
    if desc_heading:
        desc_p = desc_heading.find_next_sibling("p")
        if desc_p:
            description = desc_p.get_text(strip=True)

    return {
        "title": title,
        "product_url": url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": CATALOGUE_URL,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Stage 4: Normalize + validate with a schema (Pydantic)
# ---------------------------------------------------------------------------
class BookRecord(BaseModel):
    title: str
    product_url: str
    price_text: str
    price_gbp: float
    availability_text: str
    rating_text: str
    rating_value: int
    description: Optional[str] = None
    source_page: str
    fetched_at: str


def normalize_and_validate(raw: dict):
    """Turns raw text into clean values, then checks the result against
    the schema. Returns (record_dict, None) on success, or
    (None, error_message) on failure."""
    try:
        price_gbp = float(re.sub(r"[^\d.]", "", raw["price_text"] or ""))
    except (ValueError, TypeError):
        price_gbp = None

    rating_value = RATING_WORDS.get(raw.get("rating_text"))

    candidate = {**raw, "price_gbp": price_gbp, "rating_value": rating_value}

    try:
        record = BookRecord(**candidate)
        return record.model_dump(), None
    except ValidationError as e:
        return None, str(e)


# ---------------------------------------------------------------------------
# Stage 5 + Stage 4 storage: run everything, survive failures, write report
# ---------------------------------------------------------------------------
def main():
    stats["start_time"] = datetime.now(timezone.utc).isoformat()
    start = time.time()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    urls = discover_book_urls()

    if INJECT_FAKE_URL_FOR_TESTING:
        urls.append(
            "https://books.toscrape.com/catalogue/this-page-does-not-exist_999/index.html"
        )
        print("!! Injected one fake URL on purpose to test failure handling !!\n")

    good_records = []
    bad_records = []

    for i, url in enumerate(urls, start=1):
        raw = extract_book(url, i)
        if raw is None:
            # This page failed -- it was already logged inside fetch().
            # We skip it and keep going; one bad page must not stop the run.
            continue

        record, error = normalize_and_validate(raw)
        if record:
            good_records.append(record)
            stats["valid_records"] += 1
        else:
            bad_records.append({"raw": raw, "reason": error})
            stats["invalid_records"] += 1

    # De-duplicate by canonical URL so re-running never doubles the count
    dedup = {}
    for r in good_records:
        dedup[r["product_url"]] = r
    final_records = list(dedup.values())

    with open(os.path.join(OUTPUT_DIR, "books.json"), "w", encoding="utf-8") as f:
        json.dump(final_records, f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "errors.json"), "w", encoding="utf-8") as f:
        json.dump(bad_records, f, indent=2)

    report = {
        "start_time": stats["start_time"],
        "duration_seconds": round(time.time() - start, 2),
        "pages_fetched": stats["pages_fetched"],
        "cache_hits": stats["cache_hits"],
        "valid_records": stats["valid_records"],
        "invalid_records": stats["invalid_records"],
        "failed_pages": stats["failed_pages"],
        "failed_urls": stats["failed_urls"],
    }
    with open(os.path.join(OUTPUT_DIR, "run-report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n--- RUN REPORT ---")
    print(json.dumps(report, indent=2))
    print(f"\nSaved {len(final_records)} records to output/books.json")


if __name__ == "__main__":
    main()
