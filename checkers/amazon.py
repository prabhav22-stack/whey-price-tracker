"""
amazon_fresh.py

Amazon Fresh Checker V1

Workflow
--------

Launch Playwright
        ↓
Set delivery pincode
        ↓
Login required?
        ↓
YES → Abort

NO
        ↓
Open Fresh product page
        ↓
Download rendered HTML
        ↓
Parse HTML
        ↓
Return structured result
"""

from __future__ import annotations

import re
import time
from collections import Counter
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeout,
)

# ---------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------

AMAZON_HOME = "https://www.amazon.in/"

HTML_DUMP = Path("last_fresh_page.html")

HEADLESS = True

DEFAULT_TIMEOUT = 30000

WAIT_SHORT = 500

WAIT_MEDIUM = 1500

WAIT_LONG = 3000

# ---------------------------------------------------------------------
# UTILITY FUNCTIONS
# ---------------------------------------------------------------------

PRICE_SELECTORS = {

    "priceToPay":
        "#priceToPay .a-offscreen",

    "corePriceDisplay":
        "#corePriceDisplay_desktop_feature_div .a-offscreen",

    "corePrice":
        "#corePrice_feature_div .a-offscreen",

    "desktop_buybox":
        "#desktop_buybox .a-offscreen",

    "apexPrice":
        ".apex-pricetopay-value .a-offscreen",
}


def pause(milliseconds: int):

    time.sleep(milliseconds / 1000)


def page_text(soup: BeautifulSoup) -> str:

    return soup.get_text(" ", strip=True)


def parse_rupee(text: str):

    match = re.search(
        r"₹\s*([\d,]+(?:\.\d{2})?)",
        text,
    )

    if not match:
        return None

    return float(
        match.group(1)
        .replace(",", "")
    )


def extract_title(soup: BeautifulSoup):

    selectors = [

        "#productTitle",

        "#title span",

        "#title",

        "h1 span",

        "title",

    ]

    for selector in selectors:

        node = soup.select_one(selector)

        if not node:
            continue

        title = node.get_text(
            " ",
            strip=True,
        )

        return title.replace(
            ": Amazon.in",
            "",
        ).strip()

    return None


def save_html(html: str):

    HTML_DUMP.write_text(
        html,
        encoding="utf-8",
    )
    # ---------------------------------------------------------------------
# PLAYWRIGHT SESSION
# ---------------------------------------------------------------------

class AmazonFreshBrowser:
    """
    Lightweight wrapper around Playwright.

    Responsibilities
    ----------------
    • Launch Chromium
    • Create browser context
    • Open pages
    • Close everything safely
    """

    def __init__(self, headless: bool = HEADLESS):

        self.headless = headless

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

   def start(self):

        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=150,
            args=[
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
                '--single-process',
                '--blink-settings=imagesEnabled=false'
            ]
        )

        self.context = self.browser.new_context(

            locale="en-IN",

            timezone_id="Asia/Kolkata",

            viewport={
                "width": 1366,
                "height": 900,
            },

            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0.0.0 Safari/537.36"
            ),
        )

        self.page = self.context.new_page()

        self.page.set_default_timeout(DEFAULT_TIMEOUT)

        return self.page

    def goto(self, url: str):

        return self.page.goto(
            url,
            wait_until="domcontentloaded",
        )

    def html(self):

        return self.page.content()

    def screenshot(self, filename="fresh_debug.png"):

        self.page.screenshot(
            path=filename,
            full_page=True,
        )

    def current_url(self):

        return self.page.url

    def cookies(self):

        """
        Return browser cookies.

        Later we can export these into curl_cffi.
        """

        return self.context.cookies()

    def close(self):

        try:
            if self.context:
                self.context.close()
        except Exception:
            pass

        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass

        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass

    def __enter__(self):

        self.start()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        self.close()

# ---------------------------------------------------------------------
# LOCATION / PINCODE
# ---------------------------------------------------------------------

def is_login_page(page) -> bool:
    """
    Returns True if Amazon redirected us to login.
    """

    url = page.url.lower()

    if "signin" in url:
        return True

    if "ap/signin" in url:
        return True

    try:
        if page.locator("#ap_email").count() > 0:
            return True
    except Exception:
        pass

    try:
        if page.locator("input[name='email']").count() > 0:
            return True
    except Exception:
        pass

    return False


def set_delivery_pincode(browser: AmazonFreshBrowser, pincode: str) -> bool:
    """
    Opens Amazon Fresh and sets delivery pincode.

    Returns True on success.
    Returns False if:
        - login required
        - popup couldn't be opened
        - pincode couldn't be applied
    """

    page = browser.page

    print("\nOpening Amazon...")

    page.goto(
        AMAZON_HOME,
        wait_until="domcontentloaded",
    )

    pause(WAIT_MEDIUM)

    if is_login_page(page):
        print("Login required.")
        return False

    # ----------------------------------------------------------
    # Click delivery location
    # ----------------------------------------------------------

    location_selectors = [

        "#glow-ingress-block",

        "#nav-global-location-popover-link",

        "#glow-ingress-line1",

        "[data-action='GLUXLocationSelect']",

    ]

    clicked = False

    for selector in location_selectors:

        try:

            if page.locator(selector).count():

                page.locator(selector).first.click()

                clicked = True

                break

        except Exception:
            pass

    if not clicked:

        print("Could not open location popup.")

        browser.screenshot("location_failed.png")

        return False

    pause(WAIT_LONG)

    if is_login_page(page):

        print("Amazon requested login.")

        return False

    # ----------------------------------------------------------
    # Enter pincode
    # ----------------------------------------------------------

    input_selectors = [

        "#GLUXZipUpdateInput",

        "input[type='text']",

    ]

    entered = False

    for selector in input_selectors:

        try:

            if page.locator(selector).count():

                box = page.locator(selector).first

                box.fill("")

                box.fill(pincode)

                entered = True

                break

        except Exception:
            pass

    if not entered:

        print("Could not locate pincode textbox.")

        browser.screenshot("textbox_failed.png")

        return False

# ----------------------------------------------------------
    # Apply
    # ----------------------------------------------------------

    apply_selectors = [
        "#GLUXZipUpdate",
        "#GLUXZipUpdate-announce",
        "input[type='submit']",
        "button",
    ]

    applied = False

    for selector in apply_selectors:
        try:
            if page.locator(selector).count():
                page.locator(selector).first.click()
                applied = True
                break
        except Exception:
            pass

    if not applied:
        print("Could not click Apply.")
        browser.screenshot("apply_failed.png")
        return False

    pause(4000)

    if is_login_page(page):
        print("Amazon requested login after pincode.")
        return False

    # Read location banner to verify pincode success
    banner_text = ""
    try:
        if page.locator("#glow-ingress-block").count():
            banner_text = page.locator("#glow-ingress-block").first.inner_text()
    except Exception:
        pass

    if pincode in banner_text:
        print(f"Pincode {pincode} verified successfully.")
        return True
    else:
        print(f"Pincode verification failed. Banner shows: {banner_text.strip()}")
        return False
# ---------------------------------------------------------------------
# PRODUCT PAGE
# ---------------------------------------------------------------------

def normalize_fresh_url(url: str) -> str:
    """
    Ensure the URL points to the Fresh version.

    If almBrandId already exists, leave it alone.
    Otherwise append almBrandId=ctnow.
    """

    if "almBrandId=" in url:
        return url

    separator = "&" if "?" in url else "?"

    return url + separator + "almBrandId=ctnow"


def wait_for_product_page(page):
    """
    Wait until the important parts of the page appear.
    """

    selectors = [

        "#productTitle",

        "#corePriceDisplay_desktop_feature_div",

        "#desktop_buybox",

        "#buybox",

    ]

    for selector in selectors:

        try:

            page.wait_for_selector(
                selector,
                timeout=10000,
            )

            return

        except Exception:
            pass

    pause(WAIT_LONG)


def open_fresh_product(
    browser: AmazonFreshBrowser,
    product_url: str,
) -> Optional[str]:
    """
    Opens a Fresh product page.

    Returns rendered HTML.
    Returns None on failure.
    """

    page = browser.page

    url = normalize_fresh_url(product_url)

    print("\nOpening Fresh product...")

    page.goto(
        url,
        wait_until="domcontentloaded",
    )

    pause(WAIT_MEDIUM)

    if is_login_page(page):

        print("Amazon redirected to login.")

        browser.screenshot("login_required.png")

        return None

    wait_for_product_page(page)

    pause(WAIT_MEDIUM)

    html = page.content()

    save_html(html)

    print(f"Downloaded {len(html):,} bytes")

    return html
# ---------------------------------------------------------------------
# PRICE EXTRACTION
# ---------------------------------------------------------------------

def extract_price_candidates(soup: BeautifulSoup):
    """
    Collect every price candidate from known Amazon locations.
    """

    candidates = []

    for source, selector in PRICE_SELECTORS.items():

        try:

            for node in soup.select(selector):

                price = parse_rupee(
                    node.get_text(
                        " ",
                        strip=True,
                    )
                )

                if price is None:
                    continue

                candidates.append({

                    "source": source,

                    "price": price,

                })

        except Exception:
            pass

    return candidates


def choose_best_price(candidates):
    """
    Consensus voting.

    The price appearing most frequently wins.
    """

    if not candidates:
        return None, []

    counts = Counter()

    for item in candidates:

        counts[item["price"]] += 1

    winner = counts.most_common(1)[0][0]

    sources = [

        item["source"]

        for item in candidates

        if item["price"] == winner

    ]

    return winner, sources


# ---------------------------------------------------------------------
# MRP
# ---------------------------------------------------------------------

def extract_mrp(soup: BeautifulSoup):
    html = str(soup)

    patterns = [
        r"M\.?R\.?P\.?.*?₹\s*([\d,]+(?:\.\d{2})?)",
        r"List Price.*?₹\s*([\d,]+(?:\.\d{2})?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.I | re.S)
        if match:
            return float(match.group(1).replace(",", ""))

    return None


# ---------------------------------------------------------------------
# DISCOUNT
# ---------------------------------------------------------------------

def extract_discount(soup: BeautifulSoup, price, mrp):
    # 1. Prioritize math if both exist
    if price and mrp:
        if mrp > price:
            return round(((mrp - price) / mrp) * 100)
        return 0  # If MRP equals price, there is 0% discount

    # 2. Fallback to Amazon's specific discount CSS class (no global regex)
    savings_node = soup.select_one(".savingsPercentage")
    if savings_node:
        match = re.search(r"(\d+)%", savings_node.get_text(" ", strip=True))
        if match:
            return int(match.group(1))

    return None
# ---------------------------------------------------------------------
# AVAILABILITY
# ---------------------------------------------------------------------

def extract_availability(soup: BeautifulSoup, price: float = None):
    """
    Determine whether the product is currently available.
    Logic reversed to prioritize positive signals.
    """
    body = page_text(soup).lower()

    positive_signals = [
        "in stock",
        "add to cart",
        "buy now",
        "one-time purchase",
        "subscribe & save",
    ]

    negative_signals = [
        "currently unavailable",
        "temporarily unavailable",
        "out of stock",
        "not deliverable",
        "unavailable",
    ]

    # 1. Price existence acts as an implicit positive signal
    if price is not None:
        return True

    # 2. Check for explicit positive buttons/text
    for signal in positive_signals:
        if signal in body:
            return True

    # 3. Only look for negative signals if no positive ones exist
    for signal in negative_signals:
        if signal in body:
            return False

    return None


# ---------------------------------------------------------------------
# DELIVERY
# ---------------------------------------------------------------------

def extract_delivery(soup: BeautifulSoup):
    """
    Extract the complete delivery promise.
    """
    body = page_text(soup)

    # Note the expanded capture groups `(...)` around the full phrases
    patterns = [
        r"(FREE delivery\s+[A-Za-z]+,\s+\d+\s+[A-Za-z]+)",
        r"(FREE delivery\s+[A-Za-z]+)",
        r"(Delivery\s+[A-Za-z]+,\s+\d+\s+[A-Za-z]+)",
        r"(Delivery\s+[A-Za-z]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, body, re.I)
        if match:
            return match.group(1).strip()

    return None


# ---------------------------------------------------------------------
# SELLER
# ---------------------------------------------------------------------

def extract_seller(soup: BeautifulSoup):
    """
    Extract seller name cleanly, dropping fulfillment garbage.
    """
    body = page_text(soup)

    patterns = [
        # This regex stops capturing when it hits common boundary phrases
        r"Sold by\s+(.+?)\s+(?:and\s+Fulfilled|Ships\s+from|FREE\s+delivery|Returns|\.)"
    ]

    for pattern in patterns:
        match = re.search(pattern, body, re.I | re.S)
        if match:
            seller = match.group(1)
            seller = re.sub(r"\s+", " ", seller).strip()
            if len(seller) > 80:
                seller = seller[:80]
            return seller

    return None


# ---------------------------------------------------------------------
# CONFIDENCE
# ---------------------------------------------------------------------

def calculate_confidence(

    title,

    price,

    mrp,

    availability,

    delivery,

    seller,

    price_sources,

):

    score = 0

    if title:
        score += 10

    if price:
        score += 30

    if mrp:
        score += 10

    if availability is not None:
        score += 10

    if delivery:
        score += 10

    if seller:
        score += 10

    score += min(

        len(price_sources),

        4,

    ) * 5

    return min(score, 100)


# ---------------------------------------------------------------------
# PARSER
# ---------------------------------------------------------------------

def parse_product(html: str):
    """
    Parse the rendered Amazon Fresh product page.
    """

    soup = BeautifulSoup(
        html,
        "lxml",
    )

    title = extract_title(soup)

    candidates = extract_price_candidates(soup)

    price, sources = choose_best_price(candidates)

    mrp = extract_mrp(soup)

    discount = extract_discount(
        soup,
        price,
        mrp,
    )

    # UPDATED: Pass price into the availability checker
    available = extract_availability(
        soup, 
        price
    )

    delivery = extract_delivery(soup)

    seller = extract_seller(soup)

    confidence = calculate_confidence(
        title,
        price,
        mrp,
        available,
        delivery,
        seller,
        sources,
    )

    return {
        "title": title,
        "price": price,
        "mrp": mrp,
        "discount_percent": discount,
        "available": available,
        "delivery": delivery,
        "seller": seller,
        "confidence": confidence,
        "price_sources": sources,
    }
    # ---------------------------------------------------------------------
# MAIN CHECKER
# ---------------------------------------------------------------------

def check_fresh_price(
    product_url: str,
    pincode: str,
):
    """
    Complete Amazon Fresh workflow.

    Returns a standardized result dictionary.
    """

    with AmazonFreshBrowser() as browser:

        # ----------------------------------------------------------
        # Set delivery location
        # ----------------------------------------------------------

        success = set_delivery_pincode(
            browser,
            pincode,
        )

        if not success:

            return {

                "success": False,

                "login_required": is_login_page(
                    browser.page,
                ),

                "error": "Unable to set delivery pincode.",

            }

        # ----------------------------------------------------------
        # Open Fresh product
        # ----------------------------------------------------------

        html = open_fresh_product(
            browser,
            product_url,
        )

        if html is None:

            return {

                "success": False,

                "login_required": is_login_page(
                    browser.page,
                ),

                "error": "Unable to open Amazon Fresh product.",

            }

        # ----------------------------------------------------------
        # Parse page
        # ----------------------------------------------------------

        result = parse_product(html)

        result["success"] = True

        result["source"] = "amazon_fresh"

        result["pincode"] = pincode

        result["product_url"] = product_url

        return result


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def main():

    print("=" * 70)
    print("Amazon Fresh Checker V1")
    print("=" * 70)

    product_url = input(
        "\nAmazon Fresh Product URL:\n> "
    ).strip()

    pincode = input(
        "\nDelivery Pincode:\n> "
    ).strip()

    print("\nRunning checker...\n")

    result = check_fresh_price(
        product_url,
        pincode,
    )

    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)

    if not result["success"]:

        print("Success        :", False)

        print(
            "Login Required :",
            result.get("login_required"),
        )

        print(
            "Error          :",
            result.get("error"),
        )

        return

    print("Title          :", result.get("title"))

    print("Price          :", result.get("price"))

    print("MRP            :", result.get("mrp"))

    print(
        "Discount       :",
        result.get("discount_percent"),
    )

    print(
        "Available      :",
        result.get("available"),
    )

    print(
        "Delivery       :",
        result.get("delivery"),
    )

    print(
        "Seller         :",
        result.get("seller"),
    )

    print(
        "Confidence     :",
        result.get("confidence"),
    )

    print(
        "Price Sources  :",
        ", ".join(
            result.get(
                "price_sources",
                [],
            )
        ),
    )

    print(
        "Pincode        :",
        result.get("pincode"),
    )

    print(
        "\nRendered HTML saved to:",
        HTML_DUMP,
    )


if __name__ == "__main__":

    main()
    
def check_amazon_fresh(product: dict) -> dict:
    """
    Adapter so PriceWatch can call Amazon Fresh
    exactly like every other checker.
    """

    return check_fresh_price(
        product_url=product["product_url"],
        pincode=product["pincode"],
    )
   
def check_price(product: dict) -> dict:
    """
    Standard interface expected by PriceWatch router.
    Extracts the string URL out of the database product dictionary.
    """
    url = product.get("product_url")
    
    # Replace 'scrape_amazon_product' with the exact name of your 
    # actual main scraping function inside this file!
    return scrape_amazon_product(url)