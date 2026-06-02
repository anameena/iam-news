#!/usr/bin/env python3
"""IAM News Aggregator — fetches RSS feeds, classifies by section, writes news.json."""

import json
import hashlib
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup

# ── IAM relevance keywords ─────────────────────────────────────────────────
IAM_KEYWORDS = [
    "identity","access management","iam","sso","single sign-on",
    "mfa","multi-factor","authentication","authorization","zero trust",
    "oauth","saml","ldap","active directory","azure ad","entra",
    "privileged access","pam","identity governance","iga",
    "okta","ping identity","cyberark","sailpoint","saviynt",
    "delinea","beyondtrust","forgerock","keycloak",
    "passkey","fido","webauthn","passwordless",
    "directory services","federation","idp","service provider",
    "role-based access","rbac","abac","least privilege",
    "credential","token","jwt","session management",
    "identity breach","account takeover","ato",
]

# ── Breach/credential compromise keywords ──────────────────────────────────
BREACH_KEYWORDS = [
    "credential stuffing","stolen credentials","credential theft",
    "account takeover","ato","password breach","password leak",
    "identity breach","identity theft","identity compromise",
    "phished.*admin","help desk.*phish","sim swap",
    "session token.*stolen","sso token.*theft","token hijack",
    "service account.*compromise","service account.*breach",
    "over-privileged.*breach","privilege escalat.*breach",
    "mfa bypass","mfa fatigue","push bombing",
]

# ── Whitepaper/research keywords ───────────────────────────────────────────
WHITEPAPER_KEYWORDS = [
    "whitepaper","white paper","research report","annual report",
    "magic quadrant","wave report","forrester wave","gartner",
    "survey results","state of identity","state of iam",
    "maturity model","framework","best practice guide",
    "technical guide","industry report","benchmark report",
]

# ── Tag detection patterns ─────────────────────────────────────────────────
CATEGORY_TAGS = {
    r"mfa|multi-factor|authenticat": "Authentication",
    r"zero trust": "Zero Trust",
    r"privileged|pam|cyberark|beyondtrust|delinea": "PAM",
    r"governance|iga|sailpoint|saviynt|lifecycle": "IGA",
    r"breach|attack|compromise|hack|credential stuffing|account takeover|ato": "Threat",
    r"okta|azure ad|entra|ping identity|forgerock|keycloak": "Vendor News",
    r"passkey|fido|webauthn|passwordless": "Passwordless",
    r"oauth|saml|oidc|federation|idp": "Standards & Protocols",
    r"regulation|compliance|gdpr|hipaa|sox|nist": "Compliance",
    r"rbac|abac|least privilege|access control": "Access Control",
}

# ── Attack vector detection ────────────────────────────────────────────────
VECTOR_PATTERNS = [
    (r"credential stuffing", "Credential Stuffing"),
    (r"stolen credential|credential theft|password.*stolen", "Stolen Credentials"),
    (r"phish", "Phishing"),
    (r"sim swap", "SIM Swap"),
    (r"session token|sso token", "Token Theft"),
    (r"service account", "Compromised Service Account"),
    (r"privilege escal", "Privilege Escalation"),
    (r"mfa bypass|mfa fatigue|push bomb", "MFA Bypass"),
    (r"ransomware", "Ransomware"),
    (r"supply chain", "Supply Chain"),
]

SOURCES = [
    {"name": "Okta Security Blog",      "url": "https://sec.okta.com/feed",                                                          "category": "Vendor"},
    {"name": "Auth0 Blog",              "url": "https://auth0.com/blog/rss.xml",                                                     "category": "Vendor"},
    {"name": "Microsoft Identity Blog", "url": "https://techcommunity.microsoft.com/t5/s/gxcontent/rss/board?board.id=Identity",     "category": "Vendor"},
    {"name": "CyberArk Blog",           "url": "https://www.cyberark.com/resources/blog/rss",                                        "category": "Vendor"},
    {"name": "SailPoint Blog",          "url": "https://www.sailpoint.com/blog/feed/",                                               "category": "Vendor"},
    {"name": "Ping Identity Blog",      "url": "https://www.pingidentity.com/en/resources/blog.rss",                                 "category": "Vendor"},
    {"name": "The Hacker News",         "url": "https://feeds.feedburner.com/TheHackersNews",                                        "category": "Security News"},
    {"name": "Dark Reading",            "url": "https://www.darkreading.com/rss/all.xml",                                            "category": "Security News"},
    {"name": "Krebs on Security",       "url": "https://krebsonsecurity.com/feed/",                                                  "category": "Security News"},
    {"name": "BleepingComputer",        "url": "https://www.bleepingcomputer.com/feed/",                                             "category": "Security News"},
    {"name": "SC Magazine",             "url": "https://www.scmagazine.com/rss",                                                     "category": "Security News"},
    {"name": "Identity Week",           "url": "https://identityweek.net/feed/",                                                     "category": "Industry"},
    {"name": "CISA Alerts",             "url": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json", "category": "Government", "type": "cisa_kev"},
]


def is_iam_relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in IAM_KEYWORDS)


def is_breach(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(re.search(p, text) for p in BREACH_KEYWORDS)


def is_whitepaper(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in WHITEPAPER_KEYWORDS)


def detect_section(item_category: str, title: str, summary: str) -> str:
    if is_breach(title, summary):
        return "breach"
    if is_whitepaper(title, summary):
        return "whitepaper"
    if item_category == "Vendor":
        return "vendor"
    return "news"


def detect_tags(title: str, summary: str) -> list[str]:
    text = (title + " " + summary).lower()
    tags = [tag for pattern, tag in CATEGORY_TAGS.items() if re.search(pattern, text)]
    return tags or ["General IAM"]


def detect_vector(title: str, summary: str) -> str | None:
    text = (title + " " + summary).lower()
    for pattern, label in VECTOR_PATTERNS:
        if re.search(pattern, text):
            return label
    return None


def detect_severity(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    if any(w in text for w in ["million","critical","cvss 9","cvss 10","mass","widespread"]):
        return "critical"
    if any(w in text for w in ["thousand","high","significant","large-scale"]):
        return "high"
    return "medium"


def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def clean_html(raw: str) -> str:
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
    return text[:500] + ("…" if len(text) > 500 else "")


def parse_date(entry) -> str:
    for field in ("published_parsed", "updated_parsed"):
        val = getattr(entry, field, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc).isoformat()
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
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    try:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = clean_html(entry.get("summary", "") or entry.get("description", ""))
            pub_date = parse_date(entry)

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

            section = detect_section(source["category"], title, summary)
            item = {
                "id": make_id(link),
                "title": title,
                "url": link,
                "summary": summary,
                "source": source["name"],
                "category": source["category"],
                "section": section,
                "tags": detect_tags(title, summary),
                "published": pub_date,
            }
            if section == "breach":
                item["tags"] = list({"Breach"} | set(item["tags"]))
                item["vector"] = detect_vector(title, summary)
                item["severity"] = detect_severity(title, summary)

            items.append(item)
    except Exception as e:
        print(f"  Error fetching {source['name']}: {e}")
    return items


def fetch_cisa_kev(source: dict) -> list[dict]:
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    try:
        data = requests.get(source["url"], timeout=15).json()
        for vuln in data.get("vulnerabilities", []):
            title = f"{vuln.get('cveID','')} — {vuln.get('vulnerabilityName','')}"
            combined = f"{title} {vuln.get('product','')} {vuln.get('vendorProject','')} {vuln.get('shortDescription','')}"
            if not is_iam_relevant(combined, ""):
                continue
            try:
                pub_dt = datetime.fromisoformat(vuln.get("dateAdded","")).replace(tzinfo=timezone.utc)
                if pub_dt < cutoff:
                    continue
                pub_iso = pub_dt.isoformat()
            except Exception:
                pub_iso = datetime.now(timezone.utc).isoformat()

            items.append({
                "id": make_id(vuln.get("cveID", title)),
                "title": title,
                "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
                "summary": vuln.get("shortDescription","")[:500],
                "source": source["name"],
                "category": source["category"],
                "section": "news",
                "tags": ["Vulnerability"] + detect_tags(combined, ""),
                "published": pub_iso,
            })
    except Exception as e:
        print(f"  Error fetching CISA KEV: {e}")
    return items


def deduplicate(items: list[dict]) -> list[dict]:
    seen_ids, seen_titles, result = set(), set(), []
    for item in items:
        key = re.sub(r"\W+", "", item["title"].lower())[:60]
        if item["id"] in seen_ids or key in seen_titles:
            continue
        seen_ids.add(item["id"])
        seen_titles.add(key)
        result.append(item)
    return result


def build_index(items: list[dict], key: str) -> dict[str, list[str]]:
    idx: dict[str, list[str]] = {}
    for item in items:
        vals = item[key] if isinstance(item[key], list) else [item[key]]
        for v in vals:
            idx.setdefault(v, []).append(item["id"])
    return idx


def main():
    print(f"Fetching IAM news — {datetime.now(timezone.utc).isoformat()}")
    all_items = []

    for source in SOURCES:
        print(f"  {source['name']}")
        fetcher = fetch_cisa_kev if source.get("type") == "cisa_kev" else fetch_rss
        items = fetcher(source)
        print(f"    → {len(items)} items")
        all_items.extend(items)

    all_items = deduplicate(all_items)
    all_items.sort(key=lambda x: x["published"], reverse=True)

    output = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "total": len(all_items),
        "items": all_items,
        "tag_index": build_index(all_items, "tags"),
        "category_index": build_index(all_items, "category"),
    }

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    breaches = sum(1 for i in all_items if i.get("section") == "breach")
    papers   = sum(1 for i in all_items if i.get("section") == "whitepaper")
    print(f"\nDone: {len(all_items)} total · {breaches} breaches · {papers} whitepapers → news.json")


if __name__ == "__main__":
    main()
