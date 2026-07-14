import re
from urllib.parse import parse_qs, urlparse

import requests


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}


def get_variant_id(product_url: str):
    parsed_url = urlparse(product_url)
    query = parse_qs(parsed_url.query)

    variant_values = query.get("variant")

    if not variant_values:
        return None

    return str(variant_values[0])


def get_product_json_url(product_url: str):
    parsed_url = urlparse(product_url)

    product_path = parsed_url.path.rstrip("/")

    return (
        f"{parsed_url.scheme}://"
        f"{parsed_url.netloc}"
        f"{product_path}.js"
    )


def check_nakpro(product: dict) -> dict:
    product_url = product.get("product_url", "")

    if not product_url:
        return {
            "price": None,
            "available": None,
            "source": "nakpro",
            "error": "Product URL is missing.",
        }

    variant_id = get_variant_id(product_url)

    if not variant_id:
        return {
            "price": None,
            "available": None,
            "source": "nakpro",
            "error": (
                "Nakpro URL does not contain a variant ID. "
                "Please use the exact product variant URL."
            ),
        }

    product_json_url = get_product_json_url(product_url)

    try:
        response = requests.get(
            product_json_url,
            headers=HEADERS,
            timeout=30,
        )

        response.raise_for_status()

        product_data = response.json()

    except Exception as error:
        return {
            "price": None,
            "available": None,
            "source": "nakpro",
            "error": (
                "Could not load Nakpro product data: "
                f"{error}"
            ),
        }

    variants = product_data.get("variants", [])

    for variant in variants:
        current_variant_id = str(
            variant.get("id", "")
        )

        if current_variant_id != variant_id:
            continue

        raw_price = variant.get("price")

        if raw_price is None:
            return {
                "price": None,
                "available": variant.get("available"),
                "source": "nakpro_variant",
                "error": (
                    f"Price missing for variant {variant_id}."
                ),
            }

        try:
            price = float(raw_price) / 100

        except (TypeError, ValueError):
            return {
                "price": None,
                "available": variant.get("available"),
                "source": "nakpro_variant",
                "error": (
                    "Invalid Nakpro variant price: "
                    f"{raw_price}"
                ),
            }

        return {
            "price": price,
            "available": variant.get("available"),
            "source": "nakpro_variant",
            "error": None,
        }

    return {
        "price": None,
        "available": None,
        "source": "nakpro_variant",
        "error": (
            f"Variant {variant_id} was not found "
            "in Nakpro product data."
        ),
    }