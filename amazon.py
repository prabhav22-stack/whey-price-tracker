"""
amazon.py

Amazon / Amazon Fresh product checker
Version 1

Features
--------
✓ Download product page
✓ Extract ASIN
✓ Extract title
✓ Return BeautifulSoup object for later parsing

Price extraction will be added in Version 2.
"""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup
from curl_cffi import requests


# ---------------------------------------------------------------------
# Browser fingerprint
# ---------------------------------------------------------------------

BROWSER = "chrome136"

HEADERS = {
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.amazon.in/",
}


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def extract_asin(url: str) -> Optional[str]:
    """
    Extract ASIN from any Amazon product URL.

    Examples
    --------
    https://amazon.in/dp/B07WZM3714

    https://amazon.in/.../dp/B07WZM3714/ref=...

    Returns
    -------
    B07WZM3714
    """

    match = re.search(r"/dp/([A-Z0-9]{10})", url)

    if match:
        return match.group(1)

    return None


# ---------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------

def download_page(url: str):
    """
    Download Amazon product page.

    Returns
    -------
    requests.Response
    """

    response = requests.get(
        url,
        impersonate=BROWSER,
        headers=HEADERS,
        timeout=60,
        allow_redirects=True,
    )

    response.raise_for_status()

    return response


# ---------------------------------------------------------------------
# HTML Parsing
# ---------------------------------------------------------------------

def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract product title.
    """

    selectors = [
        "#productTitle",
        "#title",
        "h1 span",
    ]

    for selector in selectors:
        tag = soup.select_one(selector)

        if tag:
            text = tag.get_text(" ", strip=True)

            if text:
                return text

    return None


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def check_price(url: str) -> dict:
    """
    Version 1

    Downloads page and extracts title only.
    """

    asin = extract_asin(url)

    if asin is None:
        return {
            "success": False,
            "error": "Could not extract ASIN",
        }

    response = download_page(url)

    soup = make_soup(response.text)

    title = extract_title(soup)

    return {
        "success": True,
        "asin": asin,
        "title": title,
        "url": response.url,
        "status_code": response.status_code,
        "html_length": len(response.text),
        "soup": soup,
    }


# ---------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------

if __name__ == "__main__":

    URL = (
        "https://www.amazon.in/"
        "Platinum-Protein-Isolate-Digestive-Supplement/"
        "dp/B07WZM3714/"
        "ref=sr_1_1_in_f3_wg_fs?"
        "almBrandId=ctnow"
    )

    result = check_price(URL)

    print("\n==============================")
    print("Amazon Checker V1")
    print("==============================\n")

    print("Success :", result["success"])

    if result["success"]:
        print("ASIN    :", result["asin"])
        print("Status  :", result["status_code"])
        print("Title   :", result["title"])
        print("URL     :", result["url"])
        print("HTML    :", result["html_length"], "bytes")
    else:
        print(result["error"])