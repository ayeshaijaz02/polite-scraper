# The Polite Scraper

A small, polite web scraper that collects book data from a practice website,
cleans it into structured JSON, checks it against a schema, and survives
broken pages without crashing.

## Target classification

- **Site:** https://books.toscrape.com
- **Why this site:** It is a public sandbox built specifically for people to
  practice web scraping on. The homepage states "We love being scraped!" and
  a warning banner confirms it is a demo site with fake data made for this
  exact purpose.
- **Scope:** Only the first 3 catalogue pages (60 books total). No other
  pages or sites are touched.
- **Data collected:** Book title, price, availability, star rating,
  description, and the page it came from.
- **robots.txt result:** The site returns a 404 (no robots file found) at
  `https://books.toscrape.com/robots.txt`. A missing file is not permission
  by itself, but combined with the site's own "We love being scraped!"
  message and its stated purpose as a scraping practice sandbox, scraping
  this site is appropriate here.

I will not reuse this code on another site without checking its rules and
terms first.

## Setup

1. Install Python 3.10+
2. Install dependencies: `pip install -r requirements.txt`

## Run

    python main.py

Run it twice — the second run reads from the cache and produces the same
60 records (idempotent).

## Record schema

Every record in `output/books.json` has: title, product_url (canonical
identity), price_text (raw), price_gbp (clean number), availability_text,
rating_text, rating_value (1-5), description (or null), source_page,
fetched_at.

## Politeness rules

- Identifies itself with a custom User-Agent header
- 10 second timeout on every request
- Waits 0.6s between real requests (cached pages need no delay)
- Checks the status code before parsing anything
- Retries once on server errors (5xx); never retries 404/403

## Ethics

This scraper only touches a site built for scraping practice. It collects
only the fields needed for this assignment. It would not be reused on a
different site without first checking that site's own rules and terms. An
official API should always be preferred over scraping when one exists.

## Why no browser was needed

The book data (title, price, rating, description) is already present in
the raw HTML the server sends back — nothing is loaded afterward by
JavaScript. Opening a real browser (like Playwright) to render the page
would only add time and memory cost with no extra data gained.

## Sample run report

```json
{
  "start_time": "2026-08-30T19:02:24.493874+00:00",
  "duration_seconds": 153.75,
  "pages_fetched": 63,
  "cache_hits": 0,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 0,
  "failed_urls": []
}
```