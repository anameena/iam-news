#!/usr/bin/env python3
"""
IAM News Aggregator
Fetches from RSS feeds, filters for IAM-relevant content, writes news.json
"""

import json
import hashlib
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup

IAM_KEYWORDS = [
    "identity", "access management", "iam", "sso", "single sign-on",
    "mfa", "multi-factor", "authentication", "authorization", "zero trust",
    "oauth", "saml", "ldap", "active directory", "azure ad", "entra",
    "privileged access", "pam", "identity governance", "iga",
    "okta", "ping identity", "cyberark", "sailpoint", "saviynt",
    "delinea", "beyondtrust", "forgerock", "keycloak",
    "passkey", "fido", "webauthn", "passwordless",
    "directory services", "federation", "idp", "service provider",
    "role-based access", "rbac", "abac", "least privilege",
    "credential", "token", "jwt", "session management",
    "identity breach", "account takeover", "ato",
]

SOURCES = [
    {
        "name": "Okta Security Blog",
        "url": "https://sec.okta.com/feed",
        "category": "Vendor",
    },
    {
        "name": "Auth0 Blog",
        "url": "https://auth0.com/blog/rss.xml",
        "category": "Vendor",
    },
    {
        "name": "Microsoft Identity Blog",
        "url": "https://techcommunity.microsoft.com/t5/s/gxcontent/rss/board?board.id=Identity",
        "category": "Vendor",
    },
    {
        "name": "The Hacker News",
        "url": "https://feeds.feedburner.com/TheHackersNews",
        "category": "Security News",
    },
    {
        "name": "Dark Reading",
        "url": "https://www.darkreading.com/rss/all.xml",
        "category": "Security News",
    },
    {
        "name": "Krebs on Security",
        "url": "https://krebsonsecurity.com/feed/",
        "category": "Security News",
    },
    {
        "name": "BleepingComputer",
        "url": "https://www.bleepingcomputer.com/feed/",
        "category": "Security News",
    },
    {
        "name": "CISA Alerts",
        "url": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
        "category": "Government",
        "type": "cisa_kev",
    },
    {
        "name": "SC Magazine",
        "url": "https://www.scmagazine.com/rss",
        "category": "Security News",
    },
    {
        "name": "Identity Week",
        "url": "https://identityweek.net/feed/",
        "category": "Industry",
    },
    {
        "name": "Ping Identity Blog",
        "url": "https://www.pingidentity.com/en/resources/blog.rss",
        "category": "Vendor",
    },
]

CATEGORY_TAGS = {
    "mfa|multi-factor|authenticat": "Authentication",
    "zero trust": "Zero Trust",
    "privileged|pam|cyberark|beyondtrust|delinea": "PAM",
    "governance|iga|sailpoint|saviynt|lifecycle": "IGA",
    "breach|attack|compromise|hack|credential stuffing|account takeover|ato": "Threat",
    "okta|azure ad|entra|ping identity|forgerock|keycloak": "Vendor News",
    "passkey|fido|webauthn|passwordless": "Passwordless",
    "oauth|saml|oidc|federation|idp": "Standards & Protocols",
    "regulation|compliance|gdpr|hipaa|sox|nist": "Compliance",
    "rbac|abac|least privilege|access control": "Access Control",
}


def is_iam_relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in IAM_KEYWORDS)


def detect_tags(title: str, summary: str) -> list[str]:
    text = (title + " " + summary).lower()
    tags = []
    for pattern, tag in CATEGORY_TAGS.items():
        if re.search(pattern, text):
            tags.append(tag)
    return tags or ["General IAM"]


def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def clean_html(raw: str) -> str:
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:400] + ("…" if len(text) > 400 else "")


def parse_date(entry) -> str:
    for field in ("published_parsed", "updated_parsed"):
        val = getattr(entry, field, None)
        if val:
            try:
                dt = datetime(*val[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass
    for field in ("published", "updated"):
        val = getattr(entry, field, None)
        if val:
            try:
                return parsedate_to_datetime(val).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()


def fetch_rss(source: dict) -> list[dict]:
    items = []
    try:
        feed = feedparser.parse(source["url"])
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        for entry in feed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary_raw = entry.get("summary", "") or entry.get("description", "")
            summary = clean_html(summary_raw)
            pub_date = parse_date(entry)

            # age filter — keep last 7 days
            try:
                pub_dt = datetime.fromisoformat(pub_date)
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                if pub_dt < cutoff:
                    continue
            except Exception:
                pass

            if not is_iam_relevant(title, summary):
                continue

            items.append({
                "id": make_id(link),
                "title": title,
                "url": link,
                "summary": summary,
                "source": source["name"],
                "category": source["category"],
                "tags": detect_tags(title, summary),
                "published": pub_date,
            })
    except Exception as e:
        print(f"  Error fetching {source['name']}: {e}")
    return items


def fetch_cisa_kev(source: dict) -> list[dict]:
    """Fetch CISA Known Exploited Vulnerabilities, filter for identity-related."""
    items = []
    try:
        resp = requests.get(source["url"], timeout=15)
        data = resp.json()
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        for vuln in data.get("vulnerabilities", []):
            title = f"{vuln.get('cveID', '')} — {vuln.get('vulnerabilityName', '')}"
            product = vuln.get("product", "")
            vendor_project = vuln.get("vendorProject", "")
            description = vuln.get("shortDescription", "")
            combined = f"{title} {product} {vendor_project} {description}"

            if not is_iam_relevant(combined, ""):
                continue

            date_added = vuln.get("dateAdded", "")
            try:
                pub_dt = datetime.fromisoformat(date_added).replace(tzinfo=timezone.utc)
                if pub_dt < cutoff:
                    continue
                pub_iso = pub_dt.isoformat()
            except Exception:
                pub_iso = datetime.now(timezone.utc).isoformat()

            url = f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog"
            items.append({
                "id": make_id(vuln.get("cveID", title)),
                "title": title,
                "url": url,
                "summary": description[:400],
                "source": source["name"],
                "category": source["category"],
                "tags": ["Vulnerability"] + detect_tags(combined, ""),
                "published": pub_iso,
            })
    except Exception as e:
        print(f"  Error fetching CISA KEV: {e}")
    return items


def deduplicate(items: list[dict]) -> list[dict]:
    seen_ids = set()
    seen_titles = set()
    result = []
    for item in items:
        title_key = re.sub(r"\W+", "", item["title"].lower())[:60]
        if item["id"] in seen_ids or title_key in seen_titles:
            continue
        seen_ids.add(item["id"])
        seen_titles.add(title_key)
        result.append(item)
    return result


def main():
    print(f"Fetching IAM news at {datetime.now(timezone.utc).isoformat()}")
    all_items = []

    for source in SOURCES:
        print(f"  Fetching: {source['name']}")
        if source.get("type") == "cisa_kev":
            items = fetch_cisa_kev(source)
        else:
            items = fetch_rss(source)
        print(f"    → {len(items)} IAM-relevant items")
        all_items.extend(items)

    all_items = deduplicate(all_items)
    all_items.sort(key=lambda x: x["published"], reverse=True)

    # Build tag index
    tag_index: dict[str, list[str]] = {}
    for item in all_items:
        for tag in item["tags"]:
            tag_index.setdefault(tag, []).append(item["id"])

    # Build category index
    category_index: dict[str, list[str]] = {}
    for item in all_items:
        category_index.setdefault(item["category"], []).append(item["id"])

    output = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "total": len(all_items),
        "items": all_items,
        "tag_index": tag_index,
        "category_index": category_index,
    }

    out_path = "news.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nDone. {len(all_items)} articles written to {out_path}")


if __name__ == "__main__":
    main()
