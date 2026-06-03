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
    # Core IAM discipline — exact phrases only, avoids generic "identity"
    '"identity and access management"',
    '"privileged access management" OR "privileged identity management"',
    '"identity governance" OR "identity governance and administration"',
    '"zero trust" AND ("identity" OR "access management")',
    # Authentication technology
    '"multi-factor authentication" OR "MFA" cybersecurity',
    '"passkey" OR "FIDO2" OR "WebAuthn" security',
    '"passwordless authentication" OR "passwordless security"',
    '"single sign-on" security OR "SSO" cybersecurity',
    # Specific PAM vendors (vendor name = strong IAM signal)
    '"CyberArk" OR "BeyondTrust" OR "Delinea" OR "Thycotic"',
    # Specific IGA vendors
    '"SailPoint" OR "Saviynt" OR "Omada Identity" OR "One Identity" identity',
    # Specific CIAM / SSO vendors
    '"Okta" cybersecurity OR "Ping Identity" OR "ForgeRock" OR "Microsoft Entra"',
    '"Azure AD" OR "Azure Active Directory" security',
    # Next-gen IAM vendors
    '"Opal Security" OR "Veza" identity OR "Permiso" OR "Astrix Security"',
    '"Aembit" OR "Clutch Security" OR "P0 Security" identity',
    # Non-human & machine identity
    '"non-human identity" OR "machine identity" OR "workload identity"',
    '"SPIFFE" OR "SPIRE" OR "secrets management" security',
    # AI and agentic identity
    '"AI agent" AND ("identity" OR "access control" OR "authorization")',
    '"agentic AI" AND ("identity" OR "access management")',
    # Credential-based attacks (tech context, exact phrases)
    '"credential stuffing" OR "credential breach" OR "stolen credentials"',
    '"account takeover" cybersecurity OR "MFA bypass" OR "SIM swap" fraud',
    '"privilege escalation" AND ("identity" OR "Active Directory" OR "IAM")',
    # Standards & compliance (IAM-specific)
    '"OAuth 2.0" vulnerability OR "SAML" security OR "OIDC" security',
    '"identity governance" compliance OR "eIDAS" OR "NIST" identity',
]

# ── Trusted domains for NewsAPI (security/tech publications only) ──────────
# NewsAPI will ONLY return articles from these domains — eliminates general
# news sites that publish unrelated content containing IAM keywords by chance.
TRUSTED_DOMAINS = ",".join([
    # Cybersecurity news
    "darkreading.com", "bleepingcomputer.com", "thehackernews.com",
    "securityweek.com", "threatpost.com", "cyberscoop.com",
    "infosecurity-magazine.com", "scmagazine.com", "krebsonsecurity.com",
    "helpnetsecurity.com", "securityboulevard.com", "govinfosecurity.com",
    "bankinfosecurity.com", "csoonline.com", "securityintelligence.com",
    "thecyberwire.com", "recordedfuture.com", "portswigger.net",
    # Tech news (IAM-aware)
    "zdnet.com", "techcrunch.com", "wired.com", "theregister.com",
    "arstechnica.com", "venturebeat.com", "techrepublic.com",
    "computerworld.com", "infoworld.com", "itpro.com",
    # Identity-specific
    "identityweek.net", "findbiometrics.com",
    # Vendor blogs / official sources
    "okta.com", "sec.okta.com", "cyberark.com", "sailpoint.com",
    "saviynt.com", "beyondtrust.com", "delinea.com", "pingidentity.com",
    "forgerock.com", "auth0.com", "opal.dev", "veza.com",
    "permiso.io", "aembit.io", "microsoft.com", "techcommunity.microsoft.com",
    # Government / standards
    "cisa.gov", "nist.gov", "ncsc.gov.uk",
])

# ── Reliable RSS-only sources (verified feeds with clean URLs) ─────────────
RSS_SOURCES = [
    {"name": "Okta Security Blog",      "url": "https://sec.okta.com/feed",                                                      "category": "Vendor"},
    {"name": "Microsoft Identity Blog", "url": "https://techcommunity.microsoft.com/t5/s/gxcontent/rss/board?board.id=Identity", "category": "Vendor"},
    {"name": "CyberArk Blog",           "url": "https://www.cyberark.com/resources/blog/rss",                                    "category": "Vendor"},
    {"name": "SailPoint Blog",          "url": "https://www.sailpoint.com/blog/feed/",                                           "category": "Vendor"},
    {"name": "CISA Alerts",             "url": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
                                                                                                                                  "category": "Government", "type": "cisa_kev"},
]

# ── IAM filtering — two-tier system ───────────────────────────────────────
#
# STRONG terms: any ONE of these guarantees IAM relevance.
# These are specific enough that false positives are extremely rare.
STRONG_IAM_TERMS = [
    # Core discipline
    "access management", "identity management", "identity governance",
    "identity and access", "identity provider", "identity platform",
    "identity security", "identity fabric", "identity posture",
    "privileged access", "privileged identity", "privileged account",
    # Protocols & standards
    "single sign-on", "sso ", " sso", "saml", "oauth", "oidc",
    "ldap", "scim", "fido2", "webauthn", "passkey",
    "active directory", "azure ad", "microsoft entra",
    # Auth & access patterns
    "multi-factor authentication", "two-factor authentication",
    "mfa bypass", "mfa fatigue", "push bombing",
    "passwordless", "zero trust network", "zero trust architecture",
    "zero trust security", "least privilege", "role-based access",
    "rbac", "abac", "just-in-time access", "jit access",
    # PAM / secrets
    "pam solution", "pam platform", "privileged access management",
    "secrets management", "secret rotation", "vault", "cyberark",
    "beyondtrust", "delinea", "thycotic",
    # IGA
    "identity governance", "access certification", "access review",
    "sailpoint", "saviynt", "omada identity", "one identity",
    # CIAM / SSO vendors
    "okta", "ping identity", "forgerock", "auth0", "onelogin",
    "ibm security verify", "rsa securid",
    # Next-gen / cloud IAM
    "opal security", "veza", "permiso", "p0 security", "astrix security",
    "entitle", "aembit", "clutch security", "brainwave",
    # Machine / non-human identity
    "non-human identity", "machine identity", "workload identity",
    "service account", "spiffe", "spire", "pod identity",
    "managed identity", "federated identity credential",
    # AI identity
    "ai agent access", "agentic ai identity", "ai workload identity",
    "llm access control", "ai identity",
    # Credential attacks (tech context)
    "credential stuffing", "credential breach", "credential theft",
    "stolen credentials", "account takeover", "ato attack",
    "identity breach", "identity theft technology",
    "sim swap", "mfa bypass", "session hijack", "token hijack",
    # Compliance / frameworks
    "identity governance and administration", "iga",
    "zero trust maturity", "nist identity", "eidas",
    # JWT / tokens
    "jwt ", " jwt", "access token", "refresh token", "bearer token",
]

# EXCLUSION terms: articles matching these (without a strong IAM term)
# are almost certainly NOT about IAM technology.
EXCLUSION_TERMS = [
    # Personal / social identity (non-tech)
    "gender identity", "sexual identity", "lgbtq identity",
    "racial identity", "ethnic identity", "cultural identity",
    "national identity", "political identity", "religious identity",
    "community identity", "group identity", "social identity",
    "personal identity", "self-identity", "individual identity",
    "indigenous identity", "tribal identity",
    "identity politics", "identity crisis", "identity formation",
    "identity development", "identity theory", "identity psychology",
    # Branding / marketing
    "brand identity", "visual identity", "corporate identity design",
    "brand strategy", "logo design", "rebranding",
    # Psychology / mental health
    "mental health", "psychology", "psychiatric", "psychologist",
    "self-esteem", "self-concept", "narcissism", "therapy",
    "dissociative identity", "personality disorder",
    # Genealogy / heritage
    "ancestry", "genealogy", "ancestral", "heritage",
    "family history", "dna test",
    # Philosophy
    "philosophy of identity", "personal essay", "existential",
    # Politics / government (non-IAM)
    "voter id", "election identity", "immigration identity",
    "refugee identity", "asylum seeker", "city renamed",
    "town renamed", "village renamed", "chief minister",
    "governor", "senator", "parliament", "congress",
    "political party", "election campaign",
    # Entertainment / sports / lifestyle
    "box office", "film festival", "celebrity", "music album",
    "sports team", "football", "cricket", "olympics",
    "fashion", "beauty", "lifestyle", "recipe", "travel destination",
    # Real estate / finance (non-security)
    "real estate", "housing market", "stock market", "cryptocurrency price",
    "bitcoin price", "nft",
    # Health (non-security)
    "vaccine", "cancer treatment", "clinical trial", "hospital",
    "medical research", "drug approval",
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
    """
    Three-layer filter:

    Layer 1 — TITLE check (strictest gate):
      The article title must contain at least one strong IAM term.
      If the headline isn't about IAM, we don't care what the body says.
      This alone eliminates articles like "Town renamed..." that only
      contain IAM keywords buried in unrelated body text.

    Layer 2 — EXCLUSION check:
      Even if the title passes, reject if non-IAM topics dominate.

    Layer 3 — BODY confirmation:
      The body must also contain at least one strong IAM term
      (filters out accidental title matches).
    """
    title_lower = title.lower()
    body_lower  = body.lower()
    full_text   = title_lower + " " + body_lower

    # ── Layer 1: Title must contain a strong IAM term ──────────────────────
    title_has_strong = any(term in title_lower for term in STRONG_IAM_TERMS)
    if not title_has_strong:
        return False

    # ── Layer 2: Exclusion check on title ─────────────────────────────────
    for excl in EXCLUSION_TERMS:
        if excl in title_lower:
            return False

    # ── Layer 3: Body must also contain at least one strong IAM term ───────
    body_has_strong = any(term in body_lower for term in STRONG_IAM_TERMS)
    if not body_has_strong:
        return False

    return True

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
            "domains":  TRUSTED_DOMAINS,   # restrict to vetted publications
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
