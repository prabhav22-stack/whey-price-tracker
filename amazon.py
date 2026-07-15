
"""
amazon.py - Version 3.0

Production-oriented Amazon / Amazon Fresh checker.

Features
--------
- Download product page (curl_cffi)
- Extract ASIN
- Extract title
- Multi-source price extraction with consensus
- MRP extraction
- Discount extraction (parsed or calculated)
- Availability detection
- Delivery extraction
- Seller extraction
- Confidence scoring
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Optional

from bs4 import BeautifulSoup
from curl_cffi import requests

BROWSER = "chrome136"
HEADERS = {
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.amazon.in/",
}

PRICE_SELECTORS = {
    "priceToPay": "#priceToPay .a-offscreen",
    "corePriceDisplay": "#corePriceDisplay_desktop_feature_div .a-offscreen",
    "corePrice": "#corePrice_feature_div .a-offscreen",
    "desktop_buybox": "#desktop_buybox .a-offscreen",
    "apexPrice": ".apex-pricetopay-value .a-offscreen",
}


def extract_asin(url: str) -> Optional[str]:
    for p in (r"/dp/([A-Z0-9]{10})", r"/gp/product/([A-Z0-9]{10})"):
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def download_page(url: str):
    r = requests.get(
        url,
        impersonate=BROWSER,
        headers=HEADERS,
        timeout=60,
        allow_redirects=True,
    )
    r.raise_for_status()
    return r


def make_soup(html: str):
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def text(node):
    return node.get_text(" ", strip=True) if node else ""


def parse_rupee(s: str):
    m = re.search(r"₹\s*([\d,]+(?:\.\d{2})?)", s)
    return float(m.group(1).replace(",", "")) if m else None


def extract_title(soup):
    for sel in ["#productTitle", "#title span", "#title", "h1 span", "title"]:
        n = soup.select_one(sel)
        if n:
            return text(n).replace(": Amazon.in", "").strip()
    return None


def extract_price_candidates(soup):
    out = []
    for name, sel in PRICE_SELECTORS.items():
        n = soup.select_one(sel)
        if not n:
            continue
        p = parse_rupee(text(n))
        if p:
            out.append({"source": name, "price": p})
    return out


def choose_best_price(candidates):
    if not candidates:
        return None, []
    counts = Counter(c["price"] for c in candidates)
    winner = counts.most_common(1)[0][0]
    sources = [c["source"] for c in candidates if c["price"] == winner]
    return winner, sources


def extract_mrp(soup):
    html = str(soup)
    m = re.search(r"M\.?R\.?P\.?.{0,80}?₹\s*([\d,]+(?:\.\d{2})?)", html, re.I | re.S)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def extract_discount(soup, price, mrp):
    html = str(soup)
    m = re.search(r"-\s*(\d+)%", html)
    if m:
        return int(m.group(1))
    if price and mrp and mrp > price:
        return round((mrp - price) / mrp * 100)
    return None


def extract_availability(soup):
    page = text(soup).lower()
    positives = ["in stock", "add to cart", "buy now"]
    negatives = ["currently unavailable", "out of stock", "temporarily unavailable"]
    if any(x in page for x in negatives):
        return False
    if any(x in page for x in positives):
        return True
    return None


def extract_delivery(soup):
    body = text(soup)
    m = re.search(r"Delivering.*?(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday).*", body)
    return m.group(0)[:120] if m else None


def extract_seller(soup):
    body = text(soup)
    m = re.search(r"Sold by\s+(.+?)\s+Ships from", body)
    if m:
        return m.group(1).strip()
    m = re.search(r"Ships from\s+(.+?)\s", body)
    if m:
        return m.group(1).strip()
    return None


def calculate_confidence(price_sources, title, mrp, availability, delivery, seller):
    score = 0
    score += min(len(price_sources), 4) * 10
    if title:
        score += 10
    if mrp:
        score += 10
    if availability is not None:
        score += 10
    if delivery:
        score += 10
    if seller:
        score += 10
    return min(score, 100)


def check_price(url: str):
    asin = extract_asin(url)
    if not asin:
        return {"success": False, "error": "Invalid Amazon URL"}

    try:
        resp = download_page(url)
    except Exception as e:
        return {"success": False, "error": str(e)}

    soup = make_soup(resp.text)

    title = extract_title(soup)
    candidates = extract_price_candidates(soup)
    price, sources = choose_best_price(candidates)
    mrp = extract_mrp(soup)
    discount = extract_discount(soup, price, mrp)
    availability = extract_availability(soup)
    delivery = extract_delivery(soup)
    seller = extract_seller(soup)
    confidence = calculate_confidence(
        sources, title, mrp, availability, delivery, seller
    )

    return {
        "success": True,
        "source": "amazon",
        "asin": asin,
        "title": title,
        "price": price,
        "mrp": mrp,
        "discount_percent": discount,
        "available": availability,
        "delivery": delivery,
        "seller": seller,
        "confidence": confidence,
        "price_sources": sources,
        "status_code": resp.status_code,
        "url": resp.url,
    }


if __name__ == "__main__":
    URL = ("https://www.amazon.in/Platinum-Protein-Isolate-Digestive-Supplement/"
           "dp/B07WZM3714/ref=sr_1_1_in_f3_wg_fs?almBrandId=ctnow")
    result = check_price(URL)
    from pprint import pprint
    pprint(result)
