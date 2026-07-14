import json
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}


def clean_price(value) -> Optional[float]:
    if value is None:
        return None

    text = str(value)

    text = text.replace(",", "")
    text = text.replace("₹", "")
    text = text.strip()

    match = re.search(r"\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def find_price_in_json(data) -> Optional[float]:
    if isinstance(data, dict):
        offers = data.get("offers")

        if isinstance(offers, dict):
            price = clean_price(offers.get("price"))

            if price is not None:
                return price

            price_specification = offers.get("priceSpecification")

            if isinstance(price_specification, dict):
                price = clean_price(
                    price_specification.get("price")
                )

                if price is not None:
                    return price

        elif isinstance(offers, list):
            for offer in offers:
                price = find_price_in_json(
                    {"offers": offer}
                )

                if price is not None:
                    return price

        if data.get("@type") == "Product":
            price = clean_price(data.get("price"))

            if price is not None:
                return price

        for value in data.values():
            price = find_price_in_json(value)

            if price is not None:
                return price

    elif isinstance(data, list):
        for item in data:
            price = find_price_in_json(item)

            if price is not None:
                return price

    return None


def extract_json_ld_price(soup) -> Optional[float]:
    scripts = soup.find_all(
        "script",
        type="application/ld+json",
    )

    for script in scripts:
        content = script.string or script.get_text()

        if not content:
            continue

        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            continue

        price = find_price_in_json(data)

        if price is not None:
            return price

    return None


def extract_meta_price(soup) -> Optional[float]:
    selectors = [
        ('meta[property="product:price:amount"]', "content"),
        ('meta[property="og:price:amount"]', "content"),
        ('meta[name="twitter:data1"]', "content"),
        ('meta[itemprop="price"]', "content"),
    ]

    for selector, attribute in selectors:
        element = soup.select_one(selector)

        if not element:
            continue

        price = clean_price(element.get(attribute))

        if price is not None:
            return price

    return None


def check_generic(product: dict) -> dict:
    url = product["product_url"]

    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=30,
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        price = extract_json_ld_price(soup)

        if price is not None:
            return {
                "price": price,
                "available": True,
                "source": "json_ld",
                "error": None,
            }

        price = extract_meta_price(soup)

        if price is not None:
            return {
                "price": price,
                "available": True,
                "source": "meta",
                "error": None,
            }

        return {
            "price": None,
            "available": None,
            "source": None,
            "error": "Price not found by generic checker.",
        }

    except requests.RequestException as error:
        return {
            "price": None,
            "available": None,
            "source": None,
            "error": str(error),
        }