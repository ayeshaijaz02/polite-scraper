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

(instructions coming as the project is built)

## Run

(coming soon)