"""Collect a lead list of web development companies (10-49 people) in London as CSV.

python examples/leads_to_csv.py            # writes london_web_developers.csv
"""

from __future__ import annotations

from clutch_scraper import Clutch, DirectoryFilters
from clutch_scraper.export import write

clutch = Clutch()
london = clutch.resolve_location("London")
result = clutch.search(
    "web-developers",
    DirectoryFilters(location_id=london.location_id, company_sizes=["10-49"], sort="reviews"),
    pages=2,
)
for name, value in result.ignored_filters:
    print(f"warning: Clutch ignored {name}={value}")

write(result.companies, "csv", "london_web_developers.csv")
with_site = sum(1 for c in result.companies if c.website)
print(
    f"{len(result.companies)} companies ({with_site} with a website) -> london_web_developers.csv"
)
