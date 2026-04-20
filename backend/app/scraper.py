import asyncio
import re
import os
import random
import httpx
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# ── Config & Stealth ──────────────────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

PROXY_LIST = os.getenv("PROXY_LIST", "").split(",") if os.getenv("PROXY_LIST") else []

# Emails to ignore: generic prefixes and asset file extensions
IGNORED_EMAIL_PREFIXES = {
    "noreply", "no-reply", "donotreply", "unsubscribe",
    "bounce", "mailer-daemon", "postmaster", "root",
}

# Emails we collect but rank lower (still keep if they're the only ones)
GENERIC_EMAIL_PREFIXES = {"support", "info", "webmaster", "admin", "hello", "contact", "sales"}

EMAIL_RE = re.compile(r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b')

# Phone: 7–15 digits, international or local format
PHONE_RE = re.compile(r'(?:(?:\+|00)\d{1,3}[\s\-.]?)?(?:\(?\d{2,4}\)?[\s\-.]?){2,}\d{3,4}(?!\d)')

# Pages most likely to have contact info — checked first
CONTACT_PATHS = ["/contact", "/contact-us", "/contacts", "/about", "/about-us", "/reach-us"]


def get_random_ua() -> str:
    return random.choice(USER_AGENTS)


def get_random_proxy() -> Optional[dict]:
    if not PROXY_LIST or not PROXY_LIST[0]:
        return None
    return {"server": random.choice(PROXY_LIST)}


# ── Email helpers ─────────────────────────────────────────────────────────────

def extract_emails_from_html(html: str, site_domain: str = "") -> List[str]:
    """
    Extract and rank email addresses from raw HTML.
    Priority: domain-specific > generic > ignored (dropped).
    Also scrapes mailto: links which are more reliable than text regex.
    """
    soup = BeautifulSoup(html, "lxml")

    found: List[str] = []

    # 1. mailto: links — most reliable
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if href.lower().startswith("mailto:"):
            email = href[7:].split("?")[0].strip().lower()
            if email and "@" in email:
                found.append(email)

    # 2. Page text regex
    text = soup.get_text(separator=" ", strip=True)
    for em in EMAIL_RE.findall(text):
        found.append(em.lower())

    # 3. Deduplicate, filter noise
    seen = set()
    priority = []
    generic = []
    for em in found:
        if em in seen:
            continue
        seen.add(em)
        prefix = em.split("@")[0]
        ext = em.split(".")[-1]

        # Skip totally ignored
        if prefix in IGNORED_EMAIL_PREFIXES:
            continue
        # Skip asset filenames (.png, .jpg, etc.)
        if ext in ("png", "jpg", "gif", "svg", "css", "js", "ico", "woff"):
            continue
        # Domain-match check: if we know the site domain, prefer matching emails
        if site_domain and site_domain in em:
            priority.insert(0, em)
        elif prefix in GENERIC_EMAIL_PREFIXES:
            generic.append(em)
        else:
            priority.append(em)

    return priority + generic  # domain-specific first, generics last


def extract_phones_from_text(text: str) -> List[str]:
    """Return cleaned phone strings with digit-count validation."""
    phones = []
    seen = set()
    for ph in PHONE_RE.findall(text):
        ph = ph.strip()
        digits = re.sub(r"\D", "", ph)
        if 7 <= len(digits) <= 15 and digits not in seen:
            seen.add(digits)
            phones.append(ph)
    return phones


# ── Lightweight fallback: httpx (no browser) ─────────────────────────────────

async def fetch_page_html(url: str, ua: str = None) -> Optional[str]:
    """Fetch a page with httpx (fast, no JS). Returns HTML or None."""
    headers = {"User-Agent": ua or get_random_ua()}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=12) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                return r.text
    except Exception:
        pass
    return None


async def enrich_from_website(website: str) -> Dict[str, str]:
    """
    Visit a company website and try to find email + phone.
    Checks homepage first, then CONTACT_PATHS in order.
    Uses cheap httpx (no browser) — fast and scalable.
    """
    if not website:
        return {"email": "", "phone": ""}

    base = website if website.startswith("http") else f"https://{website}"
    parsed = urlparse(base)
    domain = parsed.netloc.replace("www.", "")

    emails_found: List[str] = []
    phones_found: List[str] = []

    # Pages to try: homepage + common contact paths
    urls_to_try = [base] + [urljoin(base, p) for p in CONTACT_PATHS]

    for url in urls_to_try:
        html = await fetch_page_html(url)
        if not html:
            continue
        emails_found.extend(extract_emails_from_html(html, site_domain=domain))
        phones_found.extend(extract_phones_from_text(
            BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)
        ))
        # Stop early if we found a good email
        if emails_found:
            break

    # Deduplicate
    seen_e, seen_p = set(), set()
    uniq_emails = [e for e in emails_found if not (e in seen_e or seen_e.add(e))]
    uniq_phones = [p for p in phones_found if not (re.sub(r"\D","",p) in seen_p or seen_p.add(re.sub(r"\D","",p)))]

    return {
        "email": uniq_emails[0] if uniq_emails else "",
        "phone": uniq_phones[0] if uniq_phones else "",
    }


# ── WebCrawler (Playwright — for JS-heavy sites) ──────────────────────────────

class WebCrawler:
    def __init__(self, max_depth: int = 2, max_pages: int = 12):
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.visited: set = set()
        self.results: dict = {}

    async def crawl(self, start_url: str) -> Dict[str, Any]:
        self.visited = set()
        self.results = {"emails": [], "phones": [], "address": "", "company_name": ""}

        parsed = urlparse(start_url)
        domain = parsed.netloc
        base = f"{parsed.scheme}://{parsed.netloc}"

        # Prioritise contact pages upfront
        priority_queue = [(urljoin(base, p), 1) for p in CONTACT_PATHS]
        main_queue = [(start_url, 0)]
        queue = main_queue + priority_queue

        async with async_playwright() as p:
            proxy = get_random_proxy()
            browser = await p.chromium.launch(
                headless=True, 
                proxy=proxy, 
                args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu", "--disable-setuid-sandbox"]
            )
            context = await browser.new_context(
                user_agent=get_random_ua(),
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            pages_crawled = 0

            while queue and pages_crawled < self.max_pages:
                url, depth = queue.pop(0)
                if url in self.visited or depth > self.max_depth:
                    continue
                self.visited.add(url)
                pages_crawled += 1

                try:
                    page = await context.new_page()
                    for attempt in range(2):
                        try:
                            await page.goto(url, timeout=18000, wait_until="domcontentloaded")
                            break
                        except Exception:
                            if attempt == 1:
                                raise
                            await asyncio.sleep(2)

                    html = await page.content()
                    soup = BeautifulSoup(html, "lxml")

                    # Company name from title tag
                    if not self.results["company_name"] and soup.title and soup.title.string:
                        self.results["company_name"] = soup.title.string.strip().split("|")[0].strip()

                    # Emails
                    parsed_domain = urlparse(url).netloc.replace("www.", "")
                    self.results["emails"].extend(extract_emails_from_html(html, site_domain=parsed_domain))

                    # Phones
                    text = soup.get_text(separator=" ", strip=True)
                    self.results["phones"].extend(extract_phones_from_text(text))

                    # Discover more links
                    if depth < self.max_depth:
                        for link in soup.find_all("a", href=True):
                            href = link["href"]
                            full_url = urljoin(url, href)
                            if urlparse(full_url).netloc == domain and full_url not in self.visited:
                                if any(kw in href.lower() for kw in ["contact", "about", "reach"]):
                                    queue.insert(0, (full_url, depth + 1))
                                else:
                                    queue.append((full_url, depth + 1))

                    await page.close()
                except Exception as e:
                    print(f"[Crawler] Error on {url}: {e}")

            await browser.close()

        # Deduplicate collected data
        seen_e, seen_p = set(), set()
        uniq_emails = [e for e in self.results["emails"] if not (e in seen_e or seen_e.add(e))]
        uniq_phones = [p for p in self.results["phones"]
                       if not (re.sub(r"\D","",p) in seen_p or seen_p.add(re.sub(r"\D","",p)))]

        return {
            "email":        uniq_emails[0] if uniq_emails else "",
            "phone":        uniq_phones[0] if uniq_phones else "",
            "address":      self.results["address"],
            "company_name": self.results["company_name"],
        }


# ── Google Maps Scraper ───────────────────────────────────────────────────────

async def scrape_google_maps(keyword: str, location: str, max_results: int = 50) -> List[Dict[str, Any]]:
    results = []
    processed_urls = set()
    search_query = f"{keyword} in {location}"
    url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"

    async with async_playwright() as p:
        proxy = get_random_proxy()
        # Launch persistent context or just fresh browser
        browser = await p.chromium.launch(
            headless=True, 
            proxy=proxy,
            args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(
            user_agent=get_random_ua(),
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = await context.new_page()

        try:
            # Retry logic for search page
            for attempt in range(3):
                try:
                    await page.goto(url, timeout=60000)
                    # Use a more reliable selector for the feed
                    await page.wait_for_selector('div[role="feed"]', timeout=30000)
                    break
                except Exception as e:
                    if attempt == 2:
                        raise e
                    await asyncio.sleep(5 * (attempt + 1))

            # --- ROBUST SCROLLING ---
            # We scroll until we have enough unique links or we hit a limit
            unique_links: List[str] = []
            scroll_attempts = 0
            max_scroll_attempts = 25 # Increased for more results
            
            while len(unique_links) < max_results and scroll_attempts < max_scroll_attempts:
                # Target the scrollable feed specifically
                feed_handle = await page.query_selector('div[role="feed"]')
                if feed_handle:
                    await feed_handle.evaluate('el => el.scrollTop += 2000')
                else:
                    await page.mouse.wheel(0, 2000)
                
                await asyncio.sleep(2) # Wait for load
                
                elements = await page.query_selector_all('a[href*="/maps/place/"]')
                for el in elements:
                    href = await el.get_attribute("href")
                    if href and href not in unique_links:
                        unique_links.append(href)
                
                scroll_attempts += 1
                if len(unique_links) >= max_results:
                    break

            # --- ITEM PROCESSING ---
            for link in unique_links[:max_results]:
                # Skip if already processed in this batch (sanity check)
                if link in processed_urls:
                    continue
                processed_urls.add(link)

                try:
                    # Random delay to prevent blocking (rate limiting)
                    await asyncio.sleep(random.uniform(1.5, 3.5))

                    detail_page = await context.new_page()
                    await detail_page.goto(link, timeout=40000)
                    await asyncio.sleep(2)  # let dynamic content render

                    # ── Company Name ──────────────────────────────────────
                    company_name = "Unknown"
                    h1 = await detail_page.query_selector("h1")
                    if h1:
                        company_name = (await h1.inner_text()).strip()

                    detail: Dict[str, Any] = {
                        "company_name":  company_name,
                        "rating":        None,
                        "reviews_count": 0,
                        "phone":         "",
                        "website":       "",
                        "address":       "",
                        "category":      "",
                        "email":         "",
                        "status":        "unverified", # Default status as requested
                        "source":        "google_maps",
                    }

                    # ── Rating ────────────────────────────────────────────
                    rating_el = await detail_page.query_selector('span[role="img"][aria-label*="star"]')
                    if not rating_el:
                        rating_el = await detail_page.query_selector('span[role="img"]')
                    if rating_el:
                        aria = await rating_el.get_attribute("aria-label") or ""
                        m = re.search(r'(\d+(?:\.\d+)?)', aria)
                        if m:
                            detail["rating"] = float(m.group(1))

                    # Reviews count
                    reviews_el = await detail_page.query_selector('span[aria-label*="review"]')
                    if reviews_el:
                        aria = await reviews_el.get_attribute("aria-label") or ""
                        m = re.search(r'(\d[\d,]*)', aria)
                        if m:
                            detail["reviews_count"] = int(m.group(1).replace(",", ""))

                    # ── Structured button data-item-id ────────────────────
                    buttons = await detail_page.query_selector_all("button[data-item-id], a[data-item-id]")
                    for btn in buttons:
                        item_id = (await btn.get_attribute("data-item-id") or "").lower()
                        text = (await btn.inner_text()).strip()
                        href = await btn.get_attribute("href") or ""
                        if item_id == "address":
                            detail["address"] = text
                        elif "phone" in item_id:
                            detail["phone"] = text
                        elif "authority" in item_id or "web" in item_id:
                            detail["website"] = href if href.startswith("http") else text

                    # ── Category ──────────────────────────────────────────
                    cat_el = await detail_page.query_selector('button[jsaction*="pane.rating.category"]')
                    if not cat_el:
                        cat_el = await detail_page.query_selector('span.DkEaL')
                    if cat_el:
                        detail["category"] = (await cat_el.inner_text()).strip()

                    # ── Email enrichment: visit website if no email yet ───
                    # Also try to scrape email from maps text first
                    page_html = await detail_page.content()
                    emails_on_page = extract_emails_from_html(page_html)
                    if emails_on_page:
                        detail["email"] = emails_on_page[0]

                    if not detail["email"] and detail["website"]:
                        enriched = await enrich_from_website(detail["website"])
                        detail["email"] = enriched.get("email", "")
                        if not detail["phone"]:
                            detail["phone"] = enriched.get("phone", "")

                    # Set final status based on contact info availability
                    if detail["email"] or detail["phone"]:
                        detail["status"] = "valid"
                    else:
                        detail["status"] = "invalid"

                    results.append(detail)
                    await detail_page.close()

                except Exception as e:
                    print(f"[Maps] Error on {link}: {e}")

        except Exception as e:
            print(f"[Maps] Search failed: {e}")
        finally:
            await browser.close()

    return results


async def scrape_site(url: str) -> Dict[str, Any]:
    """Entry point for direct URL scraping jobs."""
    crawler = WebCrawler()
    return await crawler.crawl(url)
