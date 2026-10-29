# Clutch Scraper

[![CI](https://github.com/ScrapeUnblocker/clutch-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/ScrapeUnblocker/clutch-scraper/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Powered by ScrapeUnblocker](https://img.shields.io/badge/powered%20by-ScrapeUnblocker-ff6a00)](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)

Scrape [Clutch.co](https://clutch.co), the B2B directory of agencies, software developers and IT firms, into clean JSON or CSV. List the companies in any Clutch directory with Clutch's own filters (location, hourly rate, budget, team size, industry, client type, reviews, sort), then pull full company profiles and every client review.

**Powered by [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)**: the `getPageSource` API fetches the Clutch pages and hands back the HTML, so this tool only has to read it.

## Why this exists

Clutch is where buyers shortlist service providers, which makes it a good source for vendor research, lead lists and competitor tracking. The data is spread over listing cards, profile tabs and paged reviews, and the listings have quirks: `?page=1` silently repeats page 2, unknown filter values are dropped without an error, and sponsored placements repeat companies that also rank organically. This package handles that and returns typed Python objects.

## Features

- **Directory search** for any Clutch directory: `seo-firms`, `web-developers`, `agencies/digital-marketing`, `developers/react-native`, `it-services/msp`, ... or a listing URL pasted from your browser, filters included.
- **Clutch's filters**: location (by name or id), hourly rate bands, client budget, company size, client type, industry focus, extra services, focus areas, minimum review count, verified only, Clutch Guarantee, and the six sort orders (rank, rating, reviews, name, verified, sponsored). Any other query parameter can be passed through.
- **Filter check**: Clutch echoes the filters it applied; any filter it ignored is reported instead of silently returning unfiltered results.
- **Per company**: Clutch id, name, profile URL, rating, review count, verification badge, Clutch Guarantee, min project size, hourly rate and team size (label plus numbers), location, headquarters address, phone, service mix with percentages, Clutch's summary and highlights, website (the real URL, without Clutch's tracking parameters) and logo.
- **Paging done right**: reads as many pages as you ask for, stops at the last one, de-duplicates and numbers the results. Skip paid placements with `--organic`, drop low ratings with `--min-rating`.
- **Company profiles**: description, tagline, founded year, languages, time zones, every office (address, team size, phone), service lines, focus areas, industries and client sizes with percentages, certifications, pricing snapshot and fixed-price packages, business verification details, social links, and the first page of reviews.
- **Client reviews**: title, date, overall and sub-ratings (quality, schedule, cost, willing to refer), services, project size and length, quote, summary, feedback, reviewer title, industry, location and company size, review type, and the full interview (background, challenge, solution, results). Sort by newest or rating, filter by project size, industry or service, across pages.
- **Lookups**: location ids for any place name, and every filter value of a directory with company counts.
- **Output**: JSON, JSON Lines, CSV (nested fields flattened) or a terminal table, from a CLI or as a Python library.
- **Resilient**: throttled, blocked and timed-out requests are retried with backoff; a page without Clutch data is fetched once more.

## Install

```bash
git clone https://github.com/ScrapeUnblocker/clutch-scraper.git
cd clutch-scraper
pip install .
```

Python 3.9 or newer. Runtime dependencies: the official [`scrapeunblocker`](https://pypi.org/project/scrapeunblocker/) SDK and `beautifulsoup4`.

Get an API key at [scrapeunblocker.com](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos) and put it in the environment (or copy `.env.example` to `.env` and load it your usual way):

```bash
export SCRAPEUNBLOCKER_KEY=your_key_here
```

## CLI

```bash
# Top-rated SEO companies in New York City with 10+ reviews
clutch-scraper search seo-firms --location "New York City" --sort rating --min-reviews 10 -f table

# Web developers charging $50-$149/hr with 10-49 people, three pages, as CSV
clutch-scraper search web-developers --hourly-rate 50-99,100-149 --size 10-49 -p 3 -o devs.csv

# Verified digital marketing agencies for e-commerce, midmarket clients, no sponsored slots
clutch-scraper search agencies/digital-marketing --industry ecommerce --client-type midmarket \
    --verified --organic -p 2 -o agencies.jsonl

# Paste a filtered listing straight from the browser
clutch-scraper search "https://clutch.co/developers/react-native?hourly_rate=25-49" -f table

# A full company profile
clutch-scraper profile smartsites -o smartsites.json

# The newest reviews of $10k-$50k SEO projects, three pages
clutch-scraper reviews smartsites --sort newest --project-cost 10k-50k --service seo -p 3 -o reviews.csv

# Location ids, and every filter value of a directory with counts
clutch-scraper locations "London" -f table
clutch-scraper filters seo-firms --name hourly_rate --name industries -f table
```

| Command | What it returns |
| --- | --- |
| `search` | Companies in a directory, with `--location` / `--location-id`, `--sort`, `--hourly-rate`, `--min-reviews`, `--budget`, `--size`, `--client-type`, `--industry`, `--service`, `--focus`, `--verified`, `--clutch-guarantee`, `--param NAME=VALUE`, `-p` pages, `--start-page`, `-n` limit, `--organic`, `--min-rating` |
| `profile` | Full profiles for one or more companies (slug or profile URL) |
| `reviews` | A company's reviews with `--sort relevance\|newest\|rating-high\|rating-low`, `--project-cost`, `--industry`, `--service`, `--location-id`, `-p`, `-n` |
| `locations` | Clutch location ids for a place name |
| `filters` | A directory's filter menus: every value with its company count (`--name` picks menus) |

Filter values:

| Option | Values |
| --- | --- |
| `--sort` | `rank`, `rating`, `reviews`, `name`, `verified`, `sponsored` (Clutch's default) |
| `--hourly-rate` | `0-25`, `25-49`, `50-99`, `100-149`, `150-199`, `200-300`, `300` (also `$50-$99`, `300+`, `<25`) |
| `--min-reviews` | `1`, `3`, `5`, `10`, `15`, `20` |
| `--budget` | `5000`, `10000`, `25000`, `50000`, `75000`, `100000`, `250000` (min project size fits under it) |
| `--size` | `freelancer`, `2-9`, `10-49`, `50-249`, `250-999`, `1000-9999`, `10000+` |
| `--client-type` | `small`, `midmarket`, `enterprise` |
| `--industry`, `--service`, `--focus` | slugs such as `ecommerce`, `web_design`, `field_pp_seo_local_search`; list them with `clutch-scraper filters <directory>` |

Common options: `-f json|jsonl|csv|table` (default: from the `-o` extension, else JSON), `-o FILE`, `--country` (proxy country, default `us`), `--retries`, `-v`. Run `clutch-scraper <command> -h` for details.

### Example output

```text
$ clutch-scraper search seo-firms --location "New York City" --sort rating --min-reviews 10 -n 8 -f table
location: New York City, New York (id 26002, CITY)
Top SEO Companies in New York City: 106 companies; 8 collected from 1 page(s)
rank  name                  rating  review_count  hourly_rate       min_project_size  employees  location           placement
1     Bird Marketing        5       75            $100 - $149 / hr  $5,000+           10 - 49    New York, NY       Directory
2     Breakline             5       37            $100 - $149 / hr  $1,000+           50 - 249   Brooklyn, NY       Directory
3     Zupo                  5       41            $150 - $199 / hr  $1,000+           2 - 9      New York City, NY  Directory
4     Software Pro Digital  5       46            $50 - $99 / hr    $5,000+           50 - 249   New York, NY       Directory
5     Mimvi SEO             5       27            $100 - $149 / hr  $1,000+           10 - 49    New York, NY       Directory
6     Equinox Dynamics LDA  5       64            $50 - $99 / hr    $5,000+           10 - 49    New York, NY       Directory
7     Jives Media           5       341           $100 - $149 / hr  $1,000+           10 - 49    New York, NY       Directory
8     MeanPug Digital       5       10            $100 - $149 / hr  $10,000+          10 - 49    New York, NY       Directory
```

One company from `search` as JSON (description shortened):

```json
{
  "rank": 1,
  "page": 1,
  "company_id": "188351",
  "name": "SmartSites",
  "slug": "smartsites",
  "profile_url": "https://clutch.co/profile/smartsites",
  "placement": "Sponsor",
  "sponsored": true,
  "rating": 4.9,
  "review_count": 370,
  "verification": "Premier Verified",
  "clutch_guarantee": false,
  "min_project_size": "$1,000+",
  "min_project_size_usd": 1000,
  "hourly_rate": "$100 - $149 / hr",
  "hourly_rate_min": 100,
  "hourly_rate_max": 149,
  "employees": "250 - 999",
  "employees_min": 250,
  "employees_max": 999,
  "location": "Paramus, NJ",
  "hq_street_address": "45 Eisenhower Drive",
  "hq_city": "Paramus",
  "hq_region": "NJ",
  "hq_postal_code": "07652",
  "hq_country": "US",
  "phone": "2018706000",
  "services": [
    {"name": "Search Engine Optimization", "percent": 50, "url": null},
    {"name": "Pay Per Click", "percent": 30, "url": null},
    {"name": "Advertising", "percent": 10, "url": null},
    {"name": "Social Media Marketing", "percent": 10, "url": null}
  ],
  "description": "SmartSites is a comprehensive digital marketing agency specializing in SEO, ...",
  "highlights": [],
  "website": "https://smartsites.com/lp/digital-marketing-lp/",
  "logo": "https://img.shgstatic.com/clutch-static-prod/image/scale/50x50/s3fs-public/logos/26f3b83afc3f1965a61c6cb6e144c29d_4397123236963fd0b3ccc8.svg"
}
```

`examples/review_insights.py smartsites`:

```text
SmartSites - 4.9 from 370 reviews
  $100 - $149 / hr, min project $1,000+, 250 - 999 people
  service mix: Search Engine Optimization 50%, Pay Per Click 30%, Advertising 10%, Social Media Marketing 10%

Latest 20 reviews (2026-03-06 to 2026-10-28):
  quality           4.92
  schedule          4.95
  cost              4.90
  willing to refer  4.92
  project sizes:    [('Confidential', 13), ('$10,000 to $49,999', 4), ('Less than $10,000', 3)]
  client industries: [('Other industries', 3), ('Construction', 2), ('Medical', 2)]
```

## Library

```python
from clutch_scraper import Clutch, DirectoryFilters, ReviewFilters

clutch = Clutch()  # reads SCRAPEUNBLOCKER_KEY; or Clutch(api_key="...")

# Directory search with Clutch's filters
london = clutch.resolve_location("London")
result = clutch.search(
    "web-developers",
    DirectoryFilters(
        location_id=london.location_id,
        hourly_rates=["50-99", "100-149"],
        company_sizes=["10-49"],
        min_reviews=5,
        sort="rating",
    ),
    pages=3,
    organic_only=True,
)
print(result.total, "companies;", len(result.companies), "collected")
print(result.ignored_filters)  # [] when Clutch applied every filter
for company in result.companies[:5]:
    print(company.rank, company.name, company.rating, company.hourly_rate, company.website)

# A full profile
profile = clutch.profile("smartsites")
print(profile.founded, profile.employees, [o.city for o in profile.offices])
print([(s.name, s.percent) for s in profile.service_lines])
print(profile.packages[0].name if profile.packages else None)

# Reviews, newest first, $10k-$50k projects only
reviews = clutch.reviews(
    "smartsites", ReviewFilters(sort="newest", project_cost="10k-50k"), pages=2
)
for review in reviews[:3]:
    print(review.date, review.rating, review.title, review.reviewer_industry)

# Lookups
print(clutch.find_locations("Berlin")[:3])
options = {o.name: o for o in clutch.filter_options("seo-firms")}
print([(c.label, c.value, c.count) for c in options["industries"].choices[:5]])
```

`clutch.directory_page(directory, filters, page)` returns a single page (`DirectoryPage`) with the applied-filter echo, and `clutch.reviews_page(company, filters, page)` a single review page with its total. The parsers (`parse_directory`, `parse_profile`, `parse_reviews`, ...) work on HTML you already have.

### Fields

| Object | Fields |
| --- | --- |
| `Company` | `rank`, `page`, `company_id`, `name`, `slug`, `profile_url`, `placement`, `sponsored`, `rating`, `review_count`, `verification`, `clutch_guarantee`, `min_project_size` (+ `_usd`), `hourly_rate` (+ `_min` / `_max`), `employees` (+ `_min` / `_max`), `location`, `hq_street_address`, `hq_city`, `hq_region`, `hq_postal_code`, `hq_country`, `phone`, `services`, `description`, `highlights`, `website`, `logo` |
| `Profile` | the company facts above plus `tagline`, `claimed`, `founded`, `headquarters`, `languages`, `timezones`, `offices`, `service_lines`, `focus`, `industries`, `clients`, `certifications`, `rating_for_cost`, `common_project_size`, `packages`, `verification_details`, `social`, `reviews` |
| `Review` | `review_id`, `title`, `featured`, `date`, `date_label`, `rating`, `quality`, `schedule`, `cost`, `willing_to_refer`, `services`, `project_size`, `project_length`, `quote`, `summary`, `feedback`, `reviewer_title`, `reviewer_name`, `reviewer_industry`, `reviewer_location`, `reviewer_company_size`, `review_type`, `interview`, `url` |

## Examples

| Script | What it does |
| --- | --- |
| [`examples/agency_shortlist.py`](examples/agency_shortlist.py) | Top-rated organic SEO agencies in a city with 10+ reviews and a mid-range hourly rate, as JSON |
| [`examples/leads_to_csv.py`](examples/leads_to_csv.py) | A two-page CSV lead list of 10-49 person web development companies in London |
| [`examples/review_insights.py`](examples/review_insights.py) | A company's service mix plus average sub-ratings, project sizes and client industries from its latest reviews |

## Good to know

- **Pages**: Clutch shows up to 50 companies per directory page (fewer on some location pages) and 10 reviews per review page. On the first review page Clutch may pin a "Featured Review" first; it is marked `featured` and not repeated.
- **Sponsored placements**: by default Clutch sorts sponsored companies first. Use `--sort rank` (Clutch's organic rank) or another sort, and `--organic` to skip paid slots.
- **Websites in listings**: directory cards carry a website link only for some companies. `profile` returns the website for every company that lists one.
- **Locations**: with a location filter, `location` is the office nearest to that place, while the `hq_*` fields are the headquarters. Nearby sponsors show "Serves ...".
- **Ignored filters**: an unknown filter value (a misspelt industry slug, say) is dropped by Clutch. `search` reports it in `ignored_filters`, and the CLI prints a warning.
- **`filters` is slow**: the filter-menu endpoint returns a large response and can take 20 seconds or more. The values rarely change, so look them up once.

## Project layout

```text
src/clutch_scraper/
  scraper.py    Clutch: fetching, retries, search paging, profiles, reviews, lookups
  parsing.py    directory cards, profiles, reviews, locations, filter menus -> models
  models.py     Company, Profile, Review, Office, Package, ... dataclasses
  options.py    DirectoryFilters / ReviewFilters and the accepted values
  values.py     "$100 - $149 / hr" -> (100, 149), dates -> ISO
  urls.py       clutch.co URLs (incl. the page-1 alias)
  export.py     JSON / JSONL / CSV / table output
  cli.py        the clutch-scraper command
examples/       runnable scripts
tests/          offline tests with trimmed real responses (no API calls)
```

## Development

```bash
make install   # pip install -e ".[dev]"
make lint      # ruff check + ruff format --check
make test      # pytest (offline, the SDK is mocked)
make run       # a live call: top-rated SEO companies
```

## Links

- [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)
- [API documentation](https://docs.scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)
- [Python SDK on PyPI](https://pypi.org/project/scrapeunblocker/)

This project is not affiliated with Clutch. Use it in line with Clutch's terms and applicable law.

## License

[MIT](LICENSE) © 2026 ScrapeUnblocker
