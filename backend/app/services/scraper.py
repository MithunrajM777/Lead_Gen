import asyncio
import re
import os
import random
import traceback
import concurrent.futures
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
    
# Job tracking for cancellation
active_jobs: Dict[int, bool] = {}

# Emails to ignore: generic prefixes and asset file extensions
IGNORED_EMAIL_PREFIXES = {
    "noreply", "no-reply", "donotreply", "unsubscribe",
    "bounce", "mailer-daemon", "postmaster", "root",
}

# Emails we collect but rank lower (still keep if they're the only ones)
GENERIC_EMAIL_PREFIXES = {"support", "info", "webmaster", "admin", "hello", "contact", "sales"}

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}', re.IGNORECASE)

# Phone: Must be 10–15 digits, international or local format
PHONE_RE = re.compile(r'(?:(?:\+|00)91[\s\-.]?)?(?:(?:\+|00)\d{1,3}[\s\-.]?)?(?:\(?\d{2,4}\)?[\s\-.]?){2,}\d{3,4}(?!\d)')

# Pages most likely to have contact info — checked first
CONTACT_PATHS = ["/contact", "/contact-us", "/contacts", "/about", "/about-us", "/reach-us", "/location", "/contact-details"]


def clean_domain_to_name(domain: str) -> str:
    """
    Convert domain into readable company name:
    madurasolution.com → Madura Solution
    """
    if not domain:
        return ""
    # Remove protocol if any
    name = domain.split("//")[-1] if "//" in domain else domain
    # Remove www.
    name = re.sub(r'^www\.', '', name)
    # Remove common TLDs
    name = re.sub(r'\.(com|in|org|net|co|io|biz|info|edu|gov|me|us|uk|ca|au|de|fr|jp|br)$', '', name, flags=re.IGNORECASE)
    # Replace hyphens/underscores with spaces
    name = re.sub(r'[-_]', ' ', name)
    # Split by dots if any left
    name = name.split('.')[0]
    # CamelCase to spaces
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    # Capitalize each word properly
    return name.title().strip()


def extract_address_from_html(html: str) -> Optional[str]:
    """Extract address using <address> tag, footer section, or regex."""
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    
    # 1. Check <address> tag
    addr_tag = soup.find("address")
    if addr_tag:
        text = addr_tag.get_text(separator=" ", strip=True)
        if len(text) > 10:
            return text

    # 2. Check Footer
    footer = soup.find("footer")
    if footer:
        footer_text = footer.get_text(separator=" ", strip=True)
        # Look for address keywords in footer
        if any(kw in footer_text.lower() for kw in ["address", "location", "office", "headquarters"]):
            # Use regex to find address-like pattern in footer
            # Pattern: House/Building, Street, City, State, ZIP
            match = re.search(r'[^,.\n]+,[^,.\n]+,[^,.\n]+,\s*[a-zA-Z\s]+,?\s*\d{5,6}', footer_text)
            if match:
                return match.group(0).strip()

    # 3. Broad text search for address patterns
    # Look for keywords: "address:", "location:", "office:"
    text = soup.get_text(separator=" ", strip=True)
    keywords = ["address:", "location:", "our office:", "head office:"]
    for kw in keywords:
        idx = text.lower().find(kw)
        if idx != -1:
            snippet = text[idx + len(kw):idx + len(kw) + 150].strip()
            # Try to find a reasonable ending (e.g., zip code or new line logic)
            match = re.search(r'(.+?\d{5,6})', snippet)
            if match:
                return match.group(1).strip()

    return None


def get_random_ua() -> str:
    return random.choice(USER_AGENTS)


def get_random_proxy() -> Optional[dict]:
    if not PROXY_LIST or not PROXY_LIST[0]:
        return None
    return {"server": random.choice(PROXY_LIST)}


def clean_extracted_text(text: str) -> str:
    """Remove common noise text from Google Maps results."""
    if not text:
        return ""
    # Remove common labels and noise
    noise = ["Business", "Visit", "—", "Closed", "Open 24 hours", "Verified", "Ad ·", "Website", "Directions", "Call", "Address", "Phone", "Send to your phone"]
    cleaned = text
    for n in noise:
        cleaned = cleaned.replace(n, "")
    
    # Remove Mojibake and icons (including common Google Maps icons)
    cleaned = re.sub(r'[\ue000-\uf8ff]', '', cleaned)
    cleaned = cleaned.replace("·", "").replace("•", "").replace("\n", " ").strip()
    
    # Remove category-like noise
    categories = ["Software company", "IT service", "Restaurant", "Cafe", "Hotel", "College", "School"]
    for c in categories:
        cleaned = cleaned.replace(c, "")
    
    # Remove star rating counts like (3,485)
    cleaned = re.sub(r'\(\d+[,.]?\d*\)', "", cleaned)
    
    return cleaned.strip()


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
    """Return cleaned phone strings with 10+ digit-count validation."""
    phones = []
    seen = set()
    for ph in PHONE_RE.findall(text):
        ph = ph.strip()
        digits = re.sub(r"\D", "", ph)
        # Requirement: 10+ digits
        if 10 <= len(digits) <= 15 and digits not in seen:
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
    Visit a company website and try to find email + phone + address.
    Checks homepage first, then CONTACT_PATHS in order.
    Uses cheap httpx (no browser) — fast and scalable.
    """
    if not website:
        return {"email": "", "phone": "", "address": "", "company_name": ""}

    base = website if website.startswith("http") else f"https://{website}"
    parsed = urlparse(base)
    domain = parsed.netloc.replace("www.", "")
    
    company_name = clean_domain_to_name(domain)

    emails_found: List[str] = []
    phones_found: List[str] = []
    address_found = None

    # Pages to try: homepage + common contact paths
    urls_to_try = [base] + [urljoin(base, p) for p in CONTACT_PATHS]

    for url in urls_to_try:
        html = await fetch_page_html(url)
        if not html:
            continue
        
        # Emails
        emails_found.extend(extract_emails_from_html(html, site_domain=domain))
        
        # Phones & WhatsApp Priority Logic
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(separator=" ", strip=True)
        phones_found.extend(extract_phones_from_text(text))
        
        # WhatsApp fallback search in text
        if "whatsapp" in text.lower():
            wa_matches = re.findall(r'whatsapp:?\s*(\+?\d[\d\s\-]{8,15})', text.lower())
            for wa in wa_matches:
                phones_found.append(wa.strip())

        # Address
        if not address_found:
            address_found = extract_address_from_html(html)

        # Stop early if we found a good email and address
        if emails_found and address_found:
            break

    # Deduplicate
    seen_e, seen_p = set(), set()
    uniq_emails = [e for e in emails_found if not (e in seen_e or seen_e.add(e))]
    uniq_phones = [p for p in phones_found if not (re.sub(r"\D","",p) in seen_p or seen_p.add(re.sub(r"\D","",p)))]

    return {
        "email":        uniq_emails[0] if uniq_emails else "",
        "phone":        uniq_phones[0] if uniq_phones else "",
        "address":      address_found or "",
        "company_name": company_name
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
            browser = await p.chromium.launch(headless=True, proxy=proxy)
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

                    # Phones & Address
                    text = soup.get_text(separator=" ", strip=True)
                    self.results["phones"].extend(extract_phones_from_text(text))
                    
                    if not self.results["address"]:
                        self.results["address"] = extract_address_from_html(html) or ""

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

        c_name = self.results["company_name"]
        if not c_name:
            c_name = clean_domain_to_name(urlparse(start_url).netloc)

        return {
            "email":        uniq_emails[0] if uniq_emails else "",
            "phone":        uniq_phones[0] if uniq_phones else "",
            "address":      self.results["address"],
            "company_name": c_name,
        }


# ── Google Maps Scraper ───────────────────────────────────────────────────────

DEBUG_DIR = os.path.join(os.getcwd(), "debug")
os.makedirs(DEBUG_DIR, exist_ok=True)


def _run_maps_scraper_sync(keyword: str, location: str, max_results: int,
                           job_id: Optional[int], result_queue, loop) -> None:
    """
    Stable sequential Playwright scraper with safe performance optimizations.
    """
    import asyncio as _asyncio

    async def _inner():
        search_query = f"{keyword} in {location}" if location else keyword
        url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"

        print(f"[Scraper] ====== JOB {job_id} STARTED (STABLE) ======")
        
        async with async_playwright() as p:
            proxy = get_random_proxy()
            browser = await p.chromium.launch(headless=True, proxy=proxy)
            context = await browser.new_context(
                user_agent=get_random_ua(),
                viewport={'width': 1920, 'height': 1080},
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            page = await context.new_page()

            # SAFE OPTIMIZATION: Block only images and fonts (scripts are kept)
            await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,otf}", lambda route: route.abort())

            try:
                print(f"[Scraper] Navigating to: {url}")
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
                # Wait for results to load
                try:
                    await page.wait_for_selector('div[role="feed"], [role="article"], div.Nv2PK', timeout=20000)
                except:
                    print("[Scraper] Timeout waiting for results container.")

                yielded = 0
                seen_names = set()
                scroll_rounds = 0
                max_scroll_rounds = 60
                last_cards_count = 0
                
                CARD_SELECTORS = [
                    'div[role="article"]',
                    'div.Nv2PK',
                    'a[href*="/maps/place/"]'
                ]

                while yielded < max_results and scroll_rounds < max_scroll_rounds:
                    # Check stop signal
                    if job_id is not None and not active_jobs.get(job_id, True):
                        break

                    # 1. Collect all available cards
                    cards = []
                    for sel in CARD_SELECTORS:
                        cards = await page.query_selector_all(sel)
                        if cards: break
                    
                    print(f"[Scraper] Round {scroll_rounds}: {len(cards)} cards found.")

                    # 2. Process cards sequentially
                    for card in cards:
                        if yielded >= max_results: break
                        if job_id is not None and not active_jobs.get(job_id, True): break

                        try:
                            # Scroll and click
                            await card.scroll_into_view_if_needed()
                            await card.click()
                            
                            # 4. Proper wait after clicking (1.2–1.8 seconds)
                            await _asyncio.sleep(random.uniform(1.2, 1.8))
                            
                            # Ensure detail panel is loaded
                            try:
                                await page.wait_for_selector('h1.DUwDvf', timeout=3000)
                            except: pass

                            # Extract Name (Primary Key)
                            name_el = await page.query_selector('h1.DUwDvf')
                            if not name_el: continue
                            
                            name = clean_extracted_text((await name_el.inner_text()).strip())
                            if not name or name in seen_names:
                                continue

                            # Extract Other Data
                            rating = 0.0
                            rating_el = await page.query_selector('span.MW4etd')
                            if rating_el:
                                aria = await rating_el.inner_text()
                                m = re.search(r'(\d+(?:\.\d+)?)', aria)
                                if m: rating = float(m.group(1))

                            reviews_count = 0
                            reviews_el = await page.query_selector('span.UY7F9')
                            if reviews_el:
                                aria = await reviews_el.inner_text()
                                m = re.search(r'(\d+[,.]?\d*)', aria)
                                if m: reviews_count = int(m.group(1).replace(",", "").replace(".", ""))

                            address = ""
                            address_el = await page.query_selector('button[data-item-id="address"]')
                            if address_el: address = clean_extracted_text((await address_el.inner_text()).strip())

                            phone = ""
                            phone_el = await page.query_selector('button[data-item-id^="phone"]')
                            if phone_el: phone = clean_extracted_text((await phone_el.inner_text()).strip())

                            website = None
                            website_el = await page.query_selector('a[data-item-id="authority"]')
                            if website_el: website = await website_el.get_attribute("href")

                            # Location filtering
                            if location and address:
                                if any(st in location.lower() for st in ["india", "tamil", "kerala", "karnataka", "maharashtra", "delhi"]):
                                    foreign = ["canada", "usa", "uk", "japan", "australia", "germany", "france"]
                                    if any(c in address.lower() for c in foreign) and "india" not in address.lower():
                                        continue

                            # Enrichment (Uses httpx - safe)
                            email = None
                            if website:
                                try:
                                    enrichment = await enrich_from_website(website)
                                    email = enrichment.get("email") or None
                                    if not phone and enrichment.get("phone"):
                                        phone = enrichment.get("phone")
                                except: pass

                            detail = {
                                "company_name": name, "rating": rating, "reviews_count": reviews_count,
                                "phone": phone, "website": website, "address": address,
                                "category": "Business", "email": email,
                                "status": "valid" if (email or phone) else "unverified", "source": "google_maps",
                            }

                            seen_names.add(name)
                            yielded += 1
                            print(f"[Scraper] Lead #{yielded}: {name}")
                            _asyncio.run_coroutine_threadsafe(result_queue.put(detail), loop).result()

                        except Exception as card_err:
                            print(f"[Scraper] Card error: {card_err}")

                    # 5. Scroll Optimization: Stop when no new cards load
                    if yielded < max_results:
                        if len(cards) <= last_cards_count and scroll_rounds > 5:
                            print("[Scraper] No new cards appeared. Stopping.")
                            break
                        last_cards_count = len(cards)
                        
                        await page.mouse.wheel(0, 4000)
                        await _asyncio.sleep(2.0) # Wait for cards to load
                        scroll_rounds += 1
                    else:
                        break

            except Exception as e:
                print(f"[Scraper] Main Loop Error: {e}")
                traceback.print_exc()
            finally:
                await browser.close()
                print(f"[Scraper] Browser closed. Total yielded: {yielded}")

        # Sentinel to signal completion
        _asyncio.run_coroutine_threadsafe(result_queue.put(None), loop).result()

    _asyncio.run(_inner())


async def scrape_google_maps(keyword: str, location: str, max_results: int = 50, job_id: Optional[int] = None):
    """
    Async generator — runs Playwright in a background thread to avoid
    the Windows ProactorEventLoop / NotImplementedError conflict with uvicorn.
    Yields lead dicts one at a time as they are found.
    """
    if job_id is not None:
        active_jobs[job_id] = True

    loop = asyncio.get_event_loop()
    result_queue: asyncio.Queue = asyncio.Queue()

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = loop.run_in_executor(
        executor,
        _run_maps_scraper_sync,
        keyword, location, max_results, job_id, result_queue, loop
    )

    try:
        while True:
            item = await result_queue.get()
            if item is None:
                # Sentinel — scraper finished
                break
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        # Ensure thread completes even if caller stops iterating early
        try:
            await asyncio.wait_for(future, timeout=5)
        except Exception:
            pass
        executor.shutdown(wait=False)
        if job_id is not None and job_id in active_jobs:
            del active_jobs[job_id]

async def scrape_site(url: str) -> Dict[str, Any]:
    """Entry point for direct URL scraping jobs."""
    base_url = url if url.startswith("http") else f"https://{url}"
    domain = urlparse(base_url).netloc or url
    company_name = clean_domain_to_name(domain)
    
    urls_to_visit = [base_url] + [urljoin(base_url, p) for p in CONTACT_PATHS]
    
    all_emails = set()
    all_phones = set()
    address_final = None
    
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for u in urls_to_visit:
            print(f"[Website Scraper] Visiting: {u}")
            try:
                res = await client.get(u, headers={"User-Agent": get_random_ua()})
                if res.status_code == 200:
                    html = res.text
                    soup = BeautifulSoup(html, "lxml")
                    # 1. Selective Text Extraction (Avoid meta/titles/scripts)
                    # We only care about visible text in the body
                    body = soup.find("body")
                    if not body: body = soup
                    
                    # Remove noise tags again just in case
                    for noise_tag in body(["script", "style", "nav", "header", "noscript", "meta"]):
                        noise_tag.extract()

                    # 2. Email Extraction
                    found_emails = extract_emails_from_html(html, site_domain=domain)
                    for e in found_emails: all_emails.add(e)

                    # 3. Phone Extraction
                    # Get text from common contact areas first
                    contact_sections = body.find_all(lambda tag: tag.name in ['div', 'section', 'footer', 'p'] and 
                                                   any(kw in (tag.get('id','') + tag.get('class','') if isinstance(tag.get('class'), str) else ' '.join(tag.get('class', []))).lower() 
                                                       for kw in ['contact', 'footer', 'about', 'reach', 'info']))
                    
                    if contact_sections:
                        for section in contact_sections:
                            section_text = section.get_text(separator=" ", strip=True)
                            for p in extract_phones_from_text(section_text): all_phones.add(p)
                    else:
                        # Fallback to full body text if no specific sections found
                        text = body.get_text(separator=" ", strip=True)
                        for p in extract_phones_from_text(text): all_phones.add(p)
                    
                    # 4. tel: links - High Priority
                    for a in body.find_all("a", href=True):
                        if a["href"].startswith("tel:"):
                            tel_val = a["href"].replace("tel:", "").strip()
                            digits = re.sub(r"\D", "", tel_val)
                            if 10 <= len(digits) <= 15:
                                all_phones.add(tel_val)

                    # 5. WhatsApp fallback
                    text_for_wa = body.get_text(separator=" ", strip=True)
                    if "whatsapp" in text_for_wa.lower():
                        wa_matches = re.findall(r'whatsapp:?\s*(\+?\d[\d\s\-]{8,15})', text_for_wa.lower())
                        for wa in wa_matches:
                            digits = re.sub(r"\D", "", wa)
                            if 10 <= len(digits) <= 15: all_phones.add(wa.strip())

                    # 6. Address Extraction
                    if not address_final:
                        address_final = extract_address_from_html(html)
                    
                    # Stop early if we have everything from this page
                    if all_emails and all_phones and address_final:
                        break
                        
                    await asyncio.sleep(0.3)
            except Exception as e:
                print(f"[Website Scraper] Error visiting {u}: {e}")
                
    phone_final = list(all_phones)[0] if all_phones else ""
    email_final = list(all_emails)[0] if all_emails else ""
    
    return {
        "company_name": company_name,
        "email": email_final,
        "phone": phone_final,
        "website": base_url,
        "address": address_final or "",
        "validation_status": "valid" if (email_final or phone_final) else "invalid"
    }
