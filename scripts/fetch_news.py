#!/usr/bin/env python3
"""
IAM Pulse — News Aggregator
Primary:    NewsAPI.org  (keyword search, verified URLs, fresh content)
Secondary:  Curated RSS  (Okta, Microsoft, CISA — reliably maintained feeds)
Fallback:   CISA KEV    (official government vulnerability feed)
"""

import json, hashlib, re, os, time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup

# ── API config ─────────────────────────────────────────────────────────────
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")
NEWSAPI_URL = "https://newsapi.org/v2/everything"

# ── How many days back to fetch ────────────────────────────────────────────
MAX_AGE_DAYS      = 7    # general feed
HEADLINE_AGE_DAYS = 2    # priority headlines (fresher)

# ── NewsAPI search queries (run each separately to maximise coverage) ──────
NEWSAPI_QUERIES = [
    # Core IAM
    '"identity and access management" OR "IAM" OR "zero trust identity"',
    # Authentication & MFA
    '"multi-factor authentication" OR "MFA" OR "passkey" OR "passwordless" OR "FIDO2" OR "WebAuthn"',
    # Established PAM vendors
    '"CyberArk" OR "BeyondTrust" OR "Delinea" OR "Thycotic"',
    # IGA vendors
    '"SailPoint" OR "Saviynt" OR "Omada Identity" OR "One Identity"',
    # CIAM / SSO vendors
    '"Okta" OR "Ping Identity" OR "ForgeRock" OR "Microsoft Entra" OR "Azure AD"',
    # Next-gen / cloud-native IAM
    '"Opal Security" OR "Veza" OR "Permiso" OR "P0 Security" OR "Astrix Security"',
    '"Entitle" OR "Indent" OR "Clutch Security" OR "Aembit" OR "Brainwave"',
    # AI & non-human identity
    '"non-human identity" OR "machine identity" OR "NHI" OR "AI agent access"',
    '"agentic AI" identity OR "AI workload" identity OR "secrets management" AI',
    '"SPIFFE" OR "SPIRE" OR "workload identity" OR "service mesh" identity',
    # Breaches / threats
    '"credential breach" OR "identity breach" OR "account takeover" OR "credential stuffing"',
    '"privilege escalation" identity OR "stolen credentials" OR "MFA bypass" OR "SIM swap"',
    # Standards & compliance
    '"OAuth 2.0" security OR "SAML" breach OR "OIDC" vulnerability OR "identity governance"',
    '"NIST identity" OR "eIDAS" OR "zero trust" architecture 2026',
]

# ── Reliable RSS-only sources (verified feeds with clean URLs) ─────────────
RSS_SOURCES = [
    {"name": "Okta Security Blog",      "url": "https://sec.okta.com/feed",                                                      "category": "Vendor"},
    {"name": "Microsoft Identity Blog", "url": "https://techcommunity.microsoft.com/t5/s/gxcontent/rss/board?board.id=Identity", "category": "Vendor"},
    {"name": "CyberArk Blog",           "url": "https://www.cyberark.com/resources/blog/rss",                                    "category": "Vendor"},
    {"name": "SailPoint Blog",          "url": "https://www.sailpoint.com/blog/feed/",                                           "category": "Vendor"},
    {"name": "CISA Alerts",             "url": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
                                                                                                                                  "category": "Government", "type": "cisa_kev"},
]

# ── IAM relevance keywords (for RSS fallback filtering) ────────────────────
IAM_KEYWORDS = [
    "identity","access management","iam","sso","single sign-on",
    "mfa","multi-factor","passkey","fido","webauthn","passwordless",
    "authentication","authorization","zero trust","oauth","saml","oidc",
    "ldap","active directory","azure ad","entra","privileged access",
    "pam","identity governance","iga","okta","ping identity","forgerock",
    "cyberark","sailpoint","saviynt","delinea","beyondtrust","thycotic",
    "opal security","veza","permiso","p0 security","astrix","entitle",
    "indent","aembit","clutch security","brainwave","one identity","omada",
    "non-human identity","machine identity","nhi","workload identity",
    "spiffe","spire","service account","secrets management",
    "ai agent","agentic ai","ai access","ai workload",
    "credential","token","jwt","session","rbac","abac","least privilege",
    "identity breach","account takeover","ato","credential stuffing",
]

# ── Section classification ─────────────────────────────────────────────────
BREACH_PATTERNS = [
    r"credential stuffing","stolen credential","credential theft",
    r"account takeover","ato","password breach","password leak",
    r"identity breach","identity theft","identity compromise",
    r"phish.*admin","help desk.*phish","sim swap",
    r"session token.*stolen","sso token","token hijack",
    r"service account.*comprom","over-privileged.*breach",
    r"privilege escal.*breach","mfa bypass","mfa fatigue","push bomb",
]
WHITEPAPER_PATTERNS = [
    r"whitepaper","white paper","research report","annual report",
    r"magic quadrant","forrester wave","gartner","survey results",
    r"state of identity","state of iam","maturity model",
    r"best practice","technical guide","industry report","benchmark",
]
VENDOR_NAMES = [
    "okta","microsoft entra","azure ad","ping identity","forgerock",
    "cyberark","sailpoint","saviynt","delinea","beyondtrust","thycotic",
    "opal security","veza","permiso","p0 security","astrix","entitle",
    "indent","aembit","clutch security","brainwave","one identity",
    "omada","auth0","ibm security verify","onelogin","rsa securid",
]

# ── Tag detection ──────────────────────────────────────────────────────────
TAG_PATTERNS = {
    r"mfa|multi-factor|two-factor|authenticat|passkey|fido|webauthn|passwordless": "Authentication",
    r"zero trust": "Zero Trust",
    r"pam|privileged access|cyberark|beyondtrust|delinea|thycotic": "PAM",
    r"sailpoint|saviynt|omada|one identity|identity governance|iga|lifecycle": "IGA",
    r"breach|attack|compromise|hack|credential stuffing|account takeover|ato|phish": "Threat",
    r"okta|azure ad|entra|ping identity|forgerock|auth0|ibm verify|onelogin": "Vendor News",
    r"opal|veza|permiso|p0 security|astrix|entitle|indent|aembit|clutch|brainwave": "Next-Gen IAM",
    r"non-human identity|machine identity|nhi|workload identity|spiffe|spire|service account|secrets management": "Machine Identity",
    r"ai agent|agentic ai|ai access|ai workload|llm.*access|genai.*identity": "AI Identity",
    r"oauth|saml|oidc|ldap|federation|idp|scim": "Standards & Protocols",
    r"regulation|compliance|gdpr|hipaa|sox|nist|fedramp|cmmc|eidas": "Compliance",
    r"rbac|abac|least privilege|access control|entitlement": "Access Control",
    r"vulnerability|cve|cisa|exploit|patch": "Vulnerability",
}

VECTOR_PATTERNS = [
    (r"credential stuffing", "Credential Stuffing"),
    (r"stolen credential|credential theft|password.*stolen|leaked.*password", "Stolen Credentials"),
    (r"phish", "Phishing"),
    (r"sim swap", "SIM Swap"),
    (r"session token|sso token|token hijack", "Token Theft"),
    (r"service account|over-privileged", "Compromised Service Account"),
    (r"privilege escal", "Privilege Escalation"),
    (r"mfa bypass|mfa fatigue|push bomb", "MFA Bypass"),
    (r"ransomware", "Ransomware"),
    (r"supply chain", "Supply Chain"),
    (r"insider", "Insider Threat"),
]


# ── Utilities ──────────────────────────────────────────────────────────────
def make_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:12]

def clean_html(raw: str) -> str:
    if not raw: return ""
    text = re.sub(r"\s+", " ", BeautifulSoup(raw, "html.parser").get_text(" ")).strip()
    return text[:600] + ("…" if len(text) > 600 else "")

def is_iam_relevant(title: str, body: str) -> bool:
    text = (title + " " + body).lower()
    return any(kw in text for kw in IAM_KEYWORDS)

def detect_tags(title: str, body: str) -> list[str]:
    text = (title + " " + body).lower()
    tags = [tag for pat, tag in TAG_PATTERNS.items() if re.search(pat, text)]
    return tags or ["General IAM"]

def detect_section(category: str, title: str, body: str) -> str:
    text = (title + " " + body).lower()
    if any(re.search(p, text) for p in BREACH_PATTERNS): return "breach"
    if any(re.search(p, text) for p in WHITEPAPER_PATTERNS): return "whitepaper"
    if category == "Vendor" or any(v in text for v in VENDOR_NAMES): return "vendor"
    return "news"

def detect_vector(title: str, body: str) -> str | None:
    text = (title + " " + body).lower()
    for pat, label in VECTOR_PATTERNS:
        if re.search(pat, text): return label
    return None

def detect_severity(title: str, body: str) -> str:
    text = (title + " " + body).lower()
    if any(w in text for w in ["million","critical","cvss 9","cvss 10","mass","widespread","nation-state"]): return "critical"
    if any(w in text for w in ["thousand","high","significant","large-scale","thousands"]): return "high"
    return "medium"

def validate_url(url: str, timeout: int = 5) -> bool:
    """Return True if the URL responds with a 2xx or 3xx status."""
    if not url or not url.startswith("http"): return False
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0 (compatible; IAMPulseBot/1.0)"})
        return r.status_code < 400
    except Exception:
        try:  # fallback to GET for sites that block HEAD
            r = requests.get(url, timeout=timeout, stream=True,
                             headers={"User-Agent": "Mozilla/5.0 (compatible; IAMPulseBot/1.0)"})
            return r.status_code < 400
        except Exception:
            return False

def make_item(title, url, summary, source, category, pub_iso) -> dict:
    section = detect_section(category, title, summary)
    item = {
        "id":       make_id(url or title),
        "title":    title.strip(),
        "url":      url,
        "summary":  summary,
        "source":   source,
        "category": category,
        "section":  section,
        "tags":     detect_tags(title, summary),
        "published": pub_iso,
    }
    if section == "breach":
        item["tags"]     = list({"Breach"} | set(item["tags"]))
        item["vector"]   = detect_vector(title, summary)
        item["severity"] = detect_severity(title, summary)
    return item


# ── NewsAPI fetcher ────────────────────────────────────────────────────────
def fetch_newsapi() -> list[dict]:
    if not NEWSAPI_KEY:
        print("  [NewsAPI] No API key — skipping (set NEWSAPI_KEY env var)")
        return []

    items, seen_urls = [], set()
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    from_date = cutoff.strftime("%Y-%m-%d")

    for query in NEWSAPI_QUERIES:
        params = {
            "q":        query,
            "from":     from_date,
            "sortBy":   "publishedAt",
            "language": "en",
            "pageSize": 30,
            "apiKey":   NEWSAPI_KEY,
        }
        try:
            resp = requests.get(NEWSAPI_URL, params=params, timeout=15)
            data = resp.json()
            if data.get("status") != "ok":
                print(f"  [NewsAPI] Error for query '{query[:40]}': {data.get('message','')}")
                continue

            for art in data.get("articles", []):
                url     = art.get("url", "")
                title   = art.get("title", "") or ""
                summary = art.get("description", "") or art.get("content", "") or ""
                summary = clean_html(summary)[:600]
                source  = art.get("source", {}).get("name", "News")
                pub_str = art.get("publishedAt", "")

                # Skip removed/paywalled placeholder articles
                if "[Removed]" in title or not url or url in seen_urls: continue
                if not is_iam_relevant(title, summary): continue

                try:
                    pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                    pub_iso = pub_dt.isoformat()
                except Exception:
                    pub_iso = datetime.now(timezone.utc).isoformat()

                # Determine category from source name
                src_lower = source.lower()
                if any(v in src_lower for v in ["okta","cyberark","sailpoint","ping","forgerock","microsoft","beyondtrust","delinea","saviynt"]):
                    category = "Vendor"
                elif any(v in src_lower for v in ["cisa","nist","government","gov"]):
                    category = "Government"
                elif any(v in src_lower for v in ["gartner","forrester","sans","idc","frost"]):
                    category = "Research"
                else:
                    category = "Security News"

                seen_urls.add(url)
                items.append(make_item(title, url, summary, source, category, pub_iso))

            time.sleep(0.3)  # rate limit courtesy
        except Exception as e:
            print(f"  [NewsAPI] Exception for query '{query[:40]}': {e}")

    print(f"  [NewsAPI] {len(items)} IAM-relevant articles across {len(NEWSAPI_QUERIES)} queries")
    return items


# ── RSS fetcher ────────────────────────────────────────────────────────────
def parse_rss_date(entry) -> str:
    for field in ("published_parsed", "updated_parsed"):
        val = getattr(entry, field, None)
        if val:
            try: return datetime(*val[:6], tzinfo=timezone.utc).isoformat()
            except: pass
    for field in ("published", "updated"):
        val = getattr(entry, field, None)
        if val:
            try: return parsedate_to_datetime(val).isoformat()
            except: pass
    return datetime.now(timezone.utc).isoformat()

def fetch_rss(source: dict) -> list[dict]:
    items, cutoff = [], datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    try:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries:
            title   = entry.get("title", "")
            url     = entry.get("link", "")
            summary = clean_html(entry.get("summary","") or entry.get("description",""))
            pub_iso = parse_rss_date(entry)

            try:
                pub_dt = datetime.fromisoformat(pub_iso)
                if pub_dt.tzinfo is None: pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                if pub_dt < cutoff: continue
            except: pass

            if not url or not is_iam_relevant(title, summary): continue
            items.append(make_item(title, url, summary, source["name"], source["category"], pub_iso))
    except Exception as e:
        print(f"  [RSS] Error {source['name']}: {e}")
    return items

def fetch_cisa_kev(source: dict) -> list[dict]:
    items, cutoff = [], datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    try:
        data = requests.get(source["url"], timeout=15).json()
        for v in data.get("vulnerabilities", []):
            combined = f"{v.get('cveID','')} {v.get('vulnerabilityName','')} {v.get('product','')} {v.get('vendorProject','')} {v.get('shortDescription','')}"
            if not is_iam_relevant(combined, ""): continue
            try:
                pub_dt = datetime.fromisoformat(v.get("dateAdded","")).replace(tzinfo=timezone.utc)
                if pub_dt < cutoff: continue
                pub_iso = pub_dt.isoformat()
            except:
                pub_iso = datetime.now(timezone.utc).isoformat()
            title = f"{v.get('cveID','')} — {v.get('vulnerabilityName','')}"
            url   = "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"
            items.append(make_item(title, url, v.get("shortDescription","")[:500],
                                   source["name"], source["category"], pub_iso))
    except Exception as e:
        print(f"  [CISA KEV] Error: {e}")
    return items


# ── Validate URLs ──────────────────────────────────────────────────────────
def validate_all_urls(items: list[dict]) -> list[dict]:
    print(f"  Validating {len(items)} URLs…")
    valid = []
    for item in items:
        if validate_url(item["url"]):
            valid.append(item)
        else:
            print(f"  ✗ Dead link removed: {item['url'][:80]}")
        time.sleep(0.1)
    print(f"  ✓ {len(valid)} valid links kept")
    return valid


# ── Deduplicate ────────────────────────────────────────────────────────────
def deduplicate(items: list[dict]) -> list[dict]:
    seen_ids, seen_titles, result = set(), set(), []
    for item in items:
        key = re.sub(r"\W+", "", item["title"].lower())[:70]
        if item["id"] in seen_ids or key in seen_titles: continue
        seen_ids.add(item["id"])
        seen_titles.add(key)
        result.append(item)
    return result


# ── Build indexes ──────────────────────────────────────────────────────────
def build_index(items: list[dict], key: str) -> dict[str, list[str]]:
    idx: dict[str, list[str]] = {}
    for item in items:
        vals = item[key] if isinstance(item[key], list) else [item[key]]
        for v in vals:
            idx.setdefault(v, []).append(item["id"])
    return idx


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"IAM Pulse fetch — {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}")

    all_items: list[dict] = []

    # 1. NewsAPI (primary)
    print("\n[1] NewsAPI")
    all_items.extend(fetch_newsapi())

    # 2. Curated RSS (supplement / fallback)
    print("\n[2] Curated RSS feeds")
    for source in RSS_SOURCES:
        print(f"  {source['name']}")
        fetcher = fetch_cisa_kev if source.get("type") == "cisa_kev" else fetch_rss
        items = fetcher(source)
        print(f"    → {len(items)} items")
        all_items.extend(items)

    # 3. Deduplicate before URL validation (saves requests)
    print(f"\n[3] Deduplicating ({len(all_items)} raw)…")
    all_items = deduplicate(all_items)
    print(f"    → {len(all_items)} unique articles")

    # 4. Validate URLs (skip if running in test mode)
    if os.environ.get("SKIP_URL_VALIDATION") != "1":
        print("\n[4] Validating URLs…")
        all_items = validate_all_urls(all_items)
    else:
        print("\n[4] URL validation skipped (SKIP_URL_VALIDATION=1)")

    # 5. Sort by date
    all_items.sort(key=lambda x: x["published"], reverse=True)

    # 6. Write output
    output = {
        "generated":       datetime.now(timezone.utc).isoformat(),
        "total":           len(all_items),
        "items":           all_items,
        "tag_index":       build_index(all_items, "tags"),
        "category_index":  build_index(all_items, "category"),
    }

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Summary
    sections = {}
    for item in all_items:
        sections[item["section"]] = sections.get(item["section"], 0) + 1

    print(f"\n{'='*60}")
    print(f"Done: {len(all_items)} articles → news.json")
    for s, n in sorted(sections.items()):
        print(f"  {s:12s}: {n}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
