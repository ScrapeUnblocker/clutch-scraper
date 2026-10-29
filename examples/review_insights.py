"""Summarise what clients say about a company: sub-ratings, project sizes, industries.

python examples/review_insights.py smartsites
"""

from __future__ import annotations

import sys
from collections import Counter
from statistics import mean

from clutch_scraper import Clutch, ReviewFilters

slug = sys.argv[1] if len(sys.argv) > 1 else "smartsites"
clutch = Clutch()

profile = clutch.profile(slug)
reviews = clutch.reviews(slug, ReviewFilters(sort="newest"), pages=2)
# Page 1 can start with a pinned "Featured Review", so order by date here.
reviews.sort(key=lambda r: r.date or "", reverse=True)

print(f"{profile.name} - {profile.rating} from {profile.review_count} reviews")
print(
    f"  {profile.hourly_rate}, min project {profile.min_project_size}, {profile.employees} people"
)
print("  service mix:", ", ".join(f"{s.name} {s.percent}%" for s in profile.service_lines))
print(f"\nLatest {len(reviews)} reviews ({reviews[-1].date} to {reviews[0].date}):")
for field in ("quality", "schedule", "cost", "willing_to_refer"):
    scores = [getattr(r, field) for r in reviews if getattr(r, field) is not None]
    if scores:
        print(f"  {field.replace('_', ' '):<17} {mean(scores):.2f}")
print("  project sizes:   ", Counter(r.project_size for r in reviews).most_common(3))
print("  client industries:", Counter(r.reviewer_industry for r in reviews).most_common(3))
print(f'\nNewest: "{reviews[0].quote}" - {reviews[0].reviewer_title}')
