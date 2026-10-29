"""Parse clutch.co pages into the dataclasses in :mod:`models`.

Clutch renders directories and profiles on the server, so everything is in the HTML:

* directory cards are ``#providers__list > li > div[data-clutch-pid]`` with the rating,
  highlights (min project size, hourly rate, employees, location), a services chart
  and a "Visit Website" redirect that carries the company's real URL;
* the page echoes the filters it applied in ``window.filterGetQuery``;
* profiles add JSON-LD (address, certifications, packages), ``window.chartPie``
  (service lines, focus areas, industries, clients) and server-rendered reviews.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from . import values as v
from .errors import NotFoundError, ParseError
from .models import (
    QA,
    Company,
    DirectoryPage,
    FilterChoice,
    FilterOptions,
    Location,
    Office,
    Package,
    Profile,
    Review,
    ReviewsPage,
    ServiceShare,
)
from .urls import absolute, profile_slug

_TAGS = re.compile(r"<[^>]+>")
_SHARE = re.compile(r"^(\d{1,3})%\s*(.+)$")
_MORE_SERVICES = re.compile(r"\+\s*\d+\s+services?$", re.I)
_REVIEW_ID = re.compile(r"(\d+)$")
_TOTAL_REVIEWS = re.compile(r"of\s+([\d,]+)\s+Reviews?", re.I)
_SPONSORED = ("sponsor",)
_QUOTES = '" \N{LEFT DOUBLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}'


# -- helpers ------------------------------------------------------------------------------


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def text_of(node: Tag | None, sep: str = " ") -> str | None:
    """The visible text of ``node`` with whitespace collapsed."""
    if node is None:
        return None
    return v.clean(node.get_text(sep, strip=True))


def strip_tags(html: str | None) -> str | None:
    return v.clean(_TAGS.sub(" ", html or ""))


def window_json(html: str, name: str) -> Any:
    """The JSON literal assigned to ``window.<name>`` in an inline script, or ``None``."""
    marker = re.search(r"window\." + re.escape(name) + r"\s*=\s*", html)
    if not marker:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(html, marker.end())
    except ValueError:
        return None
    return value


def is_not_found_page(soup: BeautifulSoup) -> bool:
    """Clutch's "Oops! A rare Clutch page that has 0 value" page (served with HTTP 200
    past the last directory page)."""
    h1 = soup.find("h1")
    return bool(h1 and text_of(h1) == "404")


def real_website(href: str | None) -> str | None:
    """The company URL behind a Clutch "Visit Website" redirect, without Clutch's
    ``utm_*`` tracking parameters."""
    if not href:
        return None
    parts = urlsplit(href)
    if parts.netloc.endswith("clutch.co") and parts.path.startswith("/redirect"):
        target = parse_qs(parts.query).get("u", [None])[0]
        if not target:
            return None
        parts = urlsplit(target)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    query = [(k, val) for k, val in parse_qsl(parts.query) if not k.lower().startswith("utm_")]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def _float(node: Tag | None) -> float | None:
    return v.to_float(text_of(node))


def _meta(node: Tag, prop: str) -> str | None:
    tag = node.find("meta", attrs={"itemprop": prop})
    return v.clean(tag.get("content")) if tag else None


def _tooltip(node: Tag) -> str | None:
    return strip_tags(node.get("data-tooltip-content"))


def _shares(slices: Any) -> list[ServiceShare]:
    out = []
    for item in slices or []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        pct = item.get("PercentHundreds")
        if pct is None and isinstance(item.get("percent"), (int, float)):
            pct = round(item["percent"] * 100)
        out.append(ServiceShare(name=str(item["name"]).strip(), percent=pct, url=item.get("url")))
    return out


def _ranges(company: Company | Profile) -> None:
    company.min_project_size_usd = v.money_floor(company.min_project_size)
    company.hourly_rate_min, company.hourly_rate_max = v.int_range(company.hourly_rate)
    company.employees_min, company.employees_max = v.int_range(company.employees)


def _filters_echo(html: str) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, Any]]:
    data = window_json(html, "filterGetQuery") or {}
    values: dict[str, list[str]] = {}
    labels: dict[str, list[str]] = {}
    for name, item in (data.get("Selected") or {}).items():
        picked = (item.get("values") or []) if isinstance(item, dict) else []
        values[name] = [str(p.get("value")) for p in picked if isinstance(p, dict)]
        labels[name] = [str(p.get("name")) for p in picked if isinstance(p, dict)]
    return values, labels, data


# -- directory listings ---------------------------------------------------------------------


def parse_company_card(card: Tag, *, page: int = 1, rank: int = 0) -> Company:
    """One ``div[data-clutch-pid]`` card from a directory page."""
    link = card.select_one("a.provider__title-link") or card.select_one("a.directory_profile")
    profile_url = absolute(link.get("href")) if link else None
    if not profile_url or "/profile/" not in profile_url:
        raise ParseError("company card without a profile link")
    profile_url = profile_url.split("#", 1)[0]
    placement = v.clean(card.get("data-type")) or "Directory"
    company = Company(
        rank=rank,
        page=page,
        company_id=str(card.get("data-clutch-pid") or ""),
        name=v.clean(card.get("data-title")) or text_of(link) or "",
        slug=profile_slug(profile_url),
        profile_url=profile_url,
        placement=placement,
        sponsored=any(s in placement.lower() for s in _SPONSORED),
    )

    rating = card.select_one(".provider__rating")
    if rating is not None and not card.select_one(".provider__rating--not-reviewed"):
        company.rating = _float(rating.select_one(".sg-rating__number"))
        count = _meta(rating, "reviewCount") or text_of(rating.select_one(".sg-rating__reviews"))
        company.review_count = v.to_int(count) or 0
    mark = card.select_one(".provider__verified-mark")
    company.verification = text_of(mark)
    company.clutch_guarantee = card.select_one(".provider__guarantee-mark") is not None

    def highlight(cls: str) -> Tag | None:
        return card.select_one(f".provider__highlights-item.{cls}")

    company.min_project_size = text_of(highlight("min-project-size"))
    company.hourly_rate = text_of(highlight("hourly-rate"))
    company.employees = text_of(highlight("employees-count"))
    _ranges(company)
    location = highlight("location")
    if location is not None:
        company.location = text_of(location)
        company.hq_street_address = _meta(location, "streetAddress")
        company.hq_city = _meta(location, "addressLocality")
        company.hq_region = _meta(location, "addressRegion")
        company.hq_postal_code = _meta(location, "postalCode")
        company.hq_country = _meta(location, "addressCountry")
    phone = card.find("meta", attrs={"itemprop": "telephone"})
    company.phone = v.clean(phone.get("content")) if phone else None

    for item in card.select(".provider__services-chart-item"):
        match = _SHARE.match(_tooltip(item) or "")
        if match:
            company.services.append(ServiceShare(name=match.group(2), percent=int(match.group(1))))
    if not company.services:
        for item in card.select(".provider__services-list-item-text"):
            label = _MORE_SERVICES.sub("", text_of(item) or "").strip()
            match = _SHARE.match(label)
            if match:
                company.services.append(
                    ServiceShare(name=match.group(2), percent=int(match.group(1)))
                )

    description = card.select_one(".provider__description-text-more") or card.select_one(
        ".provider__description p"
    )
    if description is not None:
        for control in description.select("button, .provider__more-container"):
            control.decompose()
    company.description = text_of(description)
    company.highlights = [
        t for t in (text_of(tab) for tab in card.select(".sg-tabs-expanded__tab")) if t
    ]
    for a in card.select("a[href]"):
        if (text_of(a) or "").lower() == "visit website" or "website-link" in " ".join(
            a.get("class") or []
        ):
            company.website = real_website(a.get("data-link") or a.get("href"))
            if company.website:
                break
    logo = card.select_one(".provider__logotype img")
    company.logo = logo.get("src") if logo else None
    return company


def _last_page(soup: BeautifulSoup, container: str) -> int | None:
    """The highest page number in a pager (Previous/Next arrows are skipped: a disabled
    Next still points one page past the end)."""
    links = soup.select(f"{container} a.sg-pagination-v2-page-number[data-page]") or [
        a
        for a in soup.select(f"{container} a[data-page]")
        if "sg-pagination-v2-page-actions" not in (a.get("class") or [])
    ]
    pages = [int(a["data-page"]) for a in links if str(a.get("data-page", "")).isdigit()]
    return max(pages) if pages else None


def _company_total(soup: BeautifulSoup) -> int | None:
    """The "83,979 Companies" counter (the Leaders Matrix block has its own counter)."""
    for node in soup.select(".navbar__companies-amount"):
        label = text_of(node) or ""
        if "compan" in label.lower():
            return v.to_int(label)
    return None


def parse_directory(html: str, *, url: str = "", page: int = 1) -> DirectoryPage:
    """A directory page (``/seo-firms``, ``/agencies/digital-marketing``, ...).

    A page past the last one comes back as Clutch's "404" page with HTTP 200; it parses
    to a page without companies.
    """
    soup = soup_of(html)
    title = text_of(soup.find("title"))
    if is_not_found_page(soup):
        return DirectoryPage(url=url, page=page, title=title, heading=None, total=0, companies=[])
    listing = soup.select_one("#providers__list")
    if listing is None:
        raise ParseError("no company list in the page (not a Clutch directory?)")
    companies = []
    seen = set()
    for card in listing.select("li.provider-list-item > [data-clutch-pid]"):
        company = parse_company_card(card, page=page)
        if company.company_id in seen:
            continue
        seen.add(company.company_id)
        companies.append(company)
    values, labels, echo = _filters_echo(html)
    canonical = soup.select_one("link[rel=canonical]")
    last = _last_page(soup, ".providers-pagination")
    return DirectoryPage(
        url=url,
        page=page,
        title=title,
        heading=text_of(soup.find("h1")),
        total=_company_total(soup),
        companies=companies,
        applied_filters=values,
        applied_labels=labels,
        clutch_url=absolute(echo.get("URL")),
        canonical_url=canonical.get("href") if canonical else None,
        has_next=bool(companies) and last is not None and page < last,
    )


# -- lookups --------------------------------------------------------------------------------


def parse_locations(body: str) -> list[Location]:
    """The JSON list from ``/directory/locations?q=...``."""
    text = body.strip()
    if text.startswith("<"):
        pre = soup_of(text).find("pre")
        text = pre.get_text() if pre else soup_of(text).get_text()
    try:
        rows = json.loads(text)
    except ValueError as exc:
        raise ParseError("the location lookup did not return JSON") from exc
    out = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or row.get("GeonaID") is None:
            continue
        out.append(
            Location(
                location_id=int(row["GeonaID"]),
                # The match is wrapped in <b>, sometimes mid-word ("<b>London</b>derry").
                name=v.clean(_TAGS.sub("", str(row.get("Name") or ""))) or "",
                type=row.get("Type") or None,
                company_count=row.get("Count"),
                population=row.get("Population"),
                has_companies=bool(row.get("HasProviders", True)),
            )
        )
    return out


def parse_facets(body: str) -> list[FilterOptions]:
    """The filter menus from ``/directory/facets?path=...`` (``#response-meta`` JSON)."""
    soup = soup_of(body)
    meta = soup.find(id="response-meta")
    try:
        data = json.loads(meta.get_text() if meta else body)
    except ValueError as exc:
        raise ParseError("no filter data in the facets response") from exc
    out = []
    for name, item in (data.get("FacetsContainer") or {}).items():
        if not isinstance(item, dict) or not item.get("choices"):
            continue
        choices = [
            FilterChoice(
                label=str(c.get("label") or c.get("slug") or c.get("value")),
                value=str(c.get("value") or c.get("slug") or ""),
                count=c.get("count") or None,
            )
            for c in item["choices"]
            if isinstance(c, dict) and str(c.get("value") or c.get("slug")) != "-1"
        ]
        title = item.get("filterName")
        out.append(
            FilterOptions(
                name=name,
                type=item.get("type") or None,
                choices=choices,
                title=title if title and title != name else None,
            )
        )
    return out


# -- reviews --------------------------------------------------------------------------------


def _interview(article: Tag) -> list[QA]:
    out = []
    for section in article.select(".profile-review__extra-section"):
        sid = section.get("id") or ""
        if sid.startswith("rating"):
            continue
        title = text_of(section.select_one(".profile-review__extra-title")) or ""
        question = None
        answer: list[str] = []
        for p in section.find_all("p"):
            if p.find("strong"):
                if question and answer:
                    out.append(
                        QA(section=title.title(), question=question, answer="\n".join(answer))
                    )
                question, answer = text_of(p), []
            elif question:
                line = text_of(p)
                if line:
                    answer.append(line)
        if question and answer:
            out.append(QA(section=title.title(), question=question, answer="\n".join(answer)))
    return out


def parse_review(article: Tag) -> Review:
    """One ``article.profile-review``."""
    share = article.select_one("[data-url]")
    url = share.get("data-url") if share else None
    review_id = article.get("data-review-id")
    if not review_id:
        match = _REVIEW_ID.search(article.get("id") or "") or _REVIEW_ID.search(url or "")
        review_id = match.group(1) if match else ""
    review = Review(
        review_id=str(review_id),
        title=text_of(article.select_one(".profile-review__header h3")),
        featured="profile-review__featured" in (article.get("class") or []),
        url=url,
    )
    for item in article.select(".profile-review__data .data--item"):
        kind = (_tooltip(item) or "").lower()
        if "service" in kind:
            review.services = [
                t for t in (text_of(s) for s in item.select(".profile-review__data-item")) if t
            ]
        elif "size" in kind:
            review.project_size = text_of(item)
        elif "length" in kind:
            review.project_length = text_of(item)
    content = article.select_one(".profile-review__content")
    if content is not None:
        review.rating = _float(content.select_one(".sg-rating__number"))
        for dl in content.select(".profile-review__rating-metrics dl"):
            label = (text_of(dl.find("dt")) or "").lower().replace(" ", "_")
            if label in {"quality", "schedule", "cost", "willing_to_refer"}:
                setattr(review, label, _float(dl.find("dd")))
    quote = text_of(article.select_one(".profile-review__quote"))
    review.quote = quote.strip(_QUOTES) if quote else None
    review.date_label = text_of(article.select_one(".profile-review__date"))
    review.date = v.iso_date(review.date_label)
    review.summary = text_of(article.select_one(".profile-review__summary"))
    review.feedback = text_of(article.select_one(".profile-review__feedback"))
    reviewer = article.select_one(".profile-review__reviewer")
    if reviewer is not None:
        review.reviewer_title = text_of(reviewer.select_one(".reviewer_position"))
        review.reviewer_name = text_of(reviewer.select_one(".reviewer_card--name"))
        for item in reviewer.select(".reviewer_list--item"):
            kind = (_tooltip(item) or "").lower()
            value = text_of(item.select_one(".reviewer_list__details-title")) or text_of(item)
            if "industry" in kind:
                review.reviewer_industry = value
            elif "location" in kind:
                review.reviewer_location = value
            elif "size" in kind:
                review.reviewer_company_size = value
            elif "type" in kind:
                review.review_type = value
    review.interview = _interview(article)
    return review


def parse_reviews(html: str, *, url: str = "", page: int = 1) -> ReviewsPage:
    """The review list of a profile page (any review page or filter)."""
    soup = soup_of(html)
    if is_not_found_page(soup):
        return ReviewsPage(url=url, page=page, reviews=[], total=0)
    articles = soup.select("#reviews-list article.profile-review") or soup.select(
        "article.profile-review"
    )
    reviews = [parse_review(a) for a in articles]
    result = text_of(soup.select_one(".profile-reviews--pagination-result"))
    match = _TOTAL_REVIEWS.search(result or "")
    echo = window_json(html, "filterGetQuery") or {}
    return ReviewsPage(
        url=url,
        page=page,
        reviews=reviews,
        total=int(match.group(1).replace(",", "")) if match else (0 if not reviews else None),
        applied=echo.get("Filter") or {},
        last_page=_last_page(soup, "#pagination-nav"),
    )


# -- profiles -------------------------------------------------------------------------------


def _json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    out = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except ValueError:
            continue
        if isinstance(data, dict):
            out.append(data)
        elif isinstance(data, list):
            out.extend(d for d in data if isinstance(d, dict))
    return out


def _list_lines(node: Tag, depth: int = 0) -> list[str]:
    """A (nested) HTML list as ``- item`` lines, indented two spaces per level."""
    lines = []
    for li in node.find_all("li", recursive=False):
        own = v.clean(
            " ".join(
                part.get_text(" ", strip=True) if isinstance(part, Tag) else str(part)
                for part in li.children
                if not (isinstance(part, Tag) and part.name in {"ul", "ol"})
            )
        )
        if own:
            lines.append(f"{'  ' * depth}- {own}")
        for sub in li.find_all(["ul", "ol"], recursive=False):
            lines.extend(_list_lines(sub, depth + 1))
    return lines


def _summary_text(node: Tag | None) -> str | None:
    """The profile summary as plain text: one line per paragraph, ``- `` for list items."""
    if node is None:
        return None
    lines: list[str] = []
    for child in node.find_all(["p", "ul", "ol", "h2", "h3", "h4"], recursive=False):
        if child.name in {"ul", "ol"}:
            lines.extend(_list_lines(child))
        else:
            line = text_of(child)
            if line:
                lines.append(line)
    if not lines:
        return text_of(node)
    return "\n".join(lines)


def _offices(section: Tag | None) -> list[Office]:
    offices = []
    for item in section.select(".profile-locations--item") if section else []:
        button = item.select_one(".profile-locations--item-button")
        label = text_of(button) or ""
        office = Office(headquarters=label.lower() == "headquarters")
        address = item.find("address")
        street_or_postal: list[str] = []
        place: list[str] = []
        for span in address.find_all("span", recursive=False) if address else []:
            nested = span.find_all("span", recursive=False)
            if nested:
                place = [t for t in (text_of(s) for s in nested) if t]
            else:
                text = text_of(span)
                if text:
                    street_or_postal.append(text)
        if place:
            office.country = place[-1]
            if len(place) >= 3:
                office.city, office.region = place[0], place[1]
            elif len(place) == 2:
                office.city = place[0]
        if not office.headquarters and button is not None:
            spans = [t for t in (text_of(s) for s in button.find_all("span")) if t]
            if spans:
                office.city = spans[0]
                office.region = spans[1] if len(spans) > 1 else office.region
        for text in street_or_postal:
            if any(ch.isalpha() for ch in text) and office.street_address is None:
                office.street_address = text
            else:
                office.postal_code = text
        office.employees = text_of(item.select_one(".employees"))
        phone = item.select_one("a.tel")
        office.phone = text_of(phone)
        offices.append(office)
    return offices


def _verification(section: Tag | None) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if section is None:
        return out
    summary = {}
    for card in section.select(".profile-verification__metrics-card"):
        label, value = text_of(card.find("dt")), text_of(card.find("dd"))
        if label and value:
            summary[label] = value
    if summary:
        out["Summary"] = summary
    for table in section.select(".profile-verification__table"):
        title = text_of(table.select_one(".profile-verification__table-title")) or "Details"
        cells = [text_of(td) for td in table.find_all("td")]
        rows = {}
        for label, value in zip(cells[0::2], cells[1::2]):
            if label and value:
                rows[label] = value
        if rows:
            out[title] = rows
    return out


def _packages(ld: list[dict[str, Any]]) -> list[Package]:
    out = []
    for block in ld:
        for product in block.get("products") or []:
            if not isinstance(product, dict) or not product.get("name"):
                continue
            offers = product.get("offers") or {}
            tiers = [
                {
                    "name": o.get("name"),
                    "price": v.to_float(str(o.get("price") or "")),
                    "currency": o.get("priceCurrency"),
                }
                for o in offers.get("offers") or []
                if isinstance(o, dict)
            ]
            out.append(
                Package(
                    name=str(product["name"]),
                    description=v.clean(product.get("description")),
                    currency=offers.get("priceCurrency"),
                    low_price=v.to_float(str(offers.get("lowPrice") or "")),
                    high_price=v.to_float(str(offers.get("highPrice") or "")),
                    tiers=tiers,
                )
            )
    return out


def parse_profile(html: str, *, url: str = "") -> Profile:
    """A company profile page (``/profile/<slug>``)."""
    soup = soup_of(html)
    header = soup.find(id="header")
    if is_not_found_page(soup) or header is None:
        raise NotFoundError(f"no Clutch profile at {url or 'this URL'}")
    ld = _json_ld(soup)
    # The company block is a LocalBusiness or another Organization subtype.
    business = next((d for d in ld if d.get("name") and d.get("url")), {})
    canonical = soup.select_one("link[rel=canonical]")
    page_url = (canonical.get("href") if canonical else None) or business.get("url") or url
    page_url = page_url.split("?", 1)[0].split("#", 1)[0]
    name = text_of(header.select_one("h1")) or business.get("name") or ""
    profile = Profile(slug=profile_slug(page_url), url=page_url, name=name)

    pid = soup.select_one("[data-clutch-pid]") or soup.select_one("[data-provider-id]")
    if pid is not None:
        profile.company_id = pid.get("data-clutch-pid") or pid.get("data-provider-id")
    else:
        match = re.search(r"[?&]pid=(\d+)", html)
        profile.company_id = match.group(1) if match else None
    for a in header.select(".website-link__item, a[href*='r.clutch.co/redirect']"):
        profile.website = real_website(a.get("data-link") or a.get("href"))
        if profile.website:
            break
    if not profile.website and isinstance(business.get("sameAs"), str):
        profile.website = business["sameAs"]
    logo = header.select_one(".profile-header__logotype img")
    profile.logo = logo.get("src") if logo else business.get("image")

    rating = business.get("aggregateRating") or {}
    profile.rating = v.to_float(str(rating.get("ratingValue") or "")) or _float(
        header.select_one(".sg-rating__number")
    )
    profile.review_count = v.to_int(str(rating.get("reviewCount") or "")) or (
        v.to_int(text_of(header.select_one(".sg-rating__reviews"))) or 0
    )
    profile.verification = text_of(header.select_one("[class*=verified-mark]")) or (
        "Premier Verified" if "Premier Verified" in (text_of(header) or "") else None
    )
    profile.clutch_guarantee = "Clutch Guarantee" in (text_of(header) or "")

    summary = soup.find(id="summary_section")
    if summary is not None:
        profile.claimed = summary.select_one(".profile-header__unclaimed") is None
        profile.tagline = text_of(summary.select_one(".profile-summary__tagline"))
        profile.description = _summary_text(summary.find(id="profile-summary-text"))
        for detail in summary.select(".profile-summary__detail"):
            label = (text_of(detail.select_one(".profile-summary__detail-label")) or "").lower()
            value = text_of(detail.select_one(".profile-summary__detail-title"))
            if label.startswith("min project"):
                profile.min_project_size = value
            elif label.startswith("hourly"):
                profile.hourly_rate = value
            elif label.startswith("employees"):
                profile.employees = value
            elif label.startswith("locations"):
                profile.headquarters = value
            elif label.startswith("year founded"):
                profile.founded = v.to_int(value)
    if not profile.description:
        profile.description = v.clean(business.get("description"))
    _ranges(profile)
    profile.languages = [
        t for t in (text_of(li) for li in soup.select("#profile-language li")) if t
    ]
    profile.timezones = [
        t for t in (text_of(dd) for dd in soup.select("#profile-timezones dd")) if t
    ]
    profile.offices = _offices(soup.find(id="location"))
    profile.phone = v.clean(str(business.get("telephone") or "")) or next(
        (o.phone for o in profile.offices if o.phone), None
    )

    chart = window_json(html, "chartPie") or {}
    profile.service_lines = _shares((chart.get("service_provided") or {}).get("slices"))
    for group in ((chart.get("focus") or {}).get("charts") or {}).values():
        if isinstance(group, dict) and group.get("slices"):
            profile.focus[str(group.get("legend_title") or "Focus")] = _shares(group["slices"])
    profile.industries = _shares((chart.get("industries") or {}).get("slices"))
    profile.clients = _shares((chart.get("clients") or {}).get("slices"))

    certs = []
    cert = business.get("hasCertification")
    for item in ([cert] if isinstance(cert, dict) else []) + list(
        business.get("hasCredential") or []
    ):
        if isinstance(item, dict) and item.get("name"):
            certs.append(v.clean(str(item["name"])) or "")
    profile.certifications = [c for c in certs if c]

    metrics = soup.find(id="metrics_section")
    for dl in metrics.find_all(["dl", "div", "li"]) if metrics is not None else []:
        if "cost" in (text_of(dl) or "").lower() and dl.find(class_="sg-rating__number"):
            profile.rating_for_cost = _float(dl.find(class_="sg-rating__number"))
            break
    if profile.rating_for_cost is None and metrics is not None:
        match = re.search(r"Rating for cost\s+([\d.]+)", text_of(metrics) or "")
        profile.rating_for_cost = float(match.group(1)) if match else None
    common = soup.find(id="common-project-size-value")
    profile.common_project_size = text_of(common.find("b") if common else None) or text_of(common)
    profile.packages = _packages(ld)
    profile.verification_details = _verification(soup.find(id="verification"))

    contact = soup.find(id="contact")
    for a in contact.select("a[href]") if contact is not None else []:
        label = text_of(a)
        href = a.get("href") or ""
        if label and href.startswith("http") and "clutch.co" not in href:
            profile.social[label] = href
    profile.reviews = parse_reviews(html, url=url).reviews
    return profile
