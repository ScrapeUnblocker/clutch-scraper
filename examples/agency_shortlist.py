"""Shortlist well-reviewed SEO agencies in one city and print them as JSON.

python examples/agency_shortlist.py "Chicago"
"""

from __future__ import annotations

import json
import sys

from clutch_scraper import Clutch, DirectoryFilters

city = sys.argv[1] if len(sys.argv) > 1 else "Chicago"
clutch = Clutch()  # reads SCRAPEUNBLOCKER_KEY

place = clutch.resolve_location(city)
filters = DirectoryFilters(
    location_id=place.location_id,
    sort="rating",
    min_reviews=10,
    hourly_rates=["50-99", "100-149"],
)
result = clutch.search("seo-firms", filters, organic_only=True, limit=10)

shortlist = [
    {
        "name": c.name,
        "rating": c.rating,
        "reviews": c.review_count,
        "hourly_rate": c.hourly_rate,
        "min_project": c.min_project_size,
        "team": c.employees,
        "location": c.location,
        "website": c.website,
        "clutch": c.profile_url,
    }
    for c in result.companies
]
print(f"{place.name}: {result.total} matching companies", file=sys.stderr)
print(json.dumps(shortlist, indent=2, ensure_ascii=False))
