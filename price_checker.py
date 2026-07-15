import os

import requests
from dotenv import load_dotenv

from checkers.generic import check_generic
from checkers.nakpro import check_nakpro
from checkers.amazon import check_price as check_amazon
from checkers.amazon_fresh import check_amazon_fresh

from database import (
    add_price_history,
    get_all_active_products,
    update_last_alerted_price,
    update_last_price,
)


load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")


if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing from .env")


CHECKERS = {
    "nakpro": check_nakpro,
    "amazon": check_amazon,
    "amazon_fresh": check_amazon_fresh,
}


def get_checker(website: str):
    # Convert to lowercase and replace spaces with underscores
    website_key = website.strip().lower().replace(" ", "_")

    return CHECKERS.get(
        website_key,
        check_generic,
    )

def check_product(product: dict) -> dict:
    website = product.get(
        "website",
        "",
    )

    checker = get_checker(website)

    return checker(product)


def send_telegram_alert(
    telegram_id,
    product_name,
    website,
    current_price,
    target_price,
    product_url,
):
    api_url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    message = (
        "🎯 TARGET PRICE REACHED!\n\n"
        f"📦 {product_name}\n"
        f"🛒 Website: {website}\n\n"
        f"💰 Current price: ₹{current_price:g}\n"
        f"🎯 Your target: ₹{target_price:g}\n\n"
        "🔥 The price is at or below your target!\n\n"
        f"🔗 {product_url}"
    )

    response = requests.post(
        api_url,
        data={
            "chat_id": str(telegram_id),
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )

    response.raise_for_status()

    telegram_response = response.json()

    if not telegram_response.get("ok"):
        raise RuntimeError(
            "Telegram rejected the alert: "
            f"{telegram_response}"
        )

    return telegram_response


def should_alert(
    current_price: float,
    target_price: float,
    last_alerted_price,
) -> bool:
    if current_price > target_price:
        return False

    if last_alerted_price is None:
        return True

    last_alerted_price = float(
        last_alerted_price
    )

    if current_price < last_alerted_price:
        return True

    return False


def process_product(product: dict):
    product_id = product["id"]

    telegram_id = product["telegram_id"]

    product_name = product.get(
        "product_name",
        "Unknown product",
    )

    website = product.get(
        "website",
        "Unknown website",
    )

    product_url = product.get(
        "product_url",
        "",
    )

    target_price = product.get(
        "target_price",
    )

    previous_price = product.get(
        "last_price",
    )

    last_alerted_price = product.get(
        "last_alerted_price",
    )

    print()
    print("=" * 60)
    print(f"Checking product ID: {product_id}")
    print(f"Product: {product_name}")
    print(f"Website: {website}")
    print(f"Target price: ₹{target_price}")

    if previous_price is None:
        print("Previous price: Not checked yet")
    else:
        print(
            f"Previous price: ₹{previous_price}"
        )

    if last_alerted_price is None:
        print(
            "Last alerted price: Never alerted"
        )
    else:
        print(
            "Last alerted price: "
            f"₹{last_alerted_price}"
        )

    result = check_product(product)

    price = result.get("price")
    available = result.get("available")
    source = result.get("source")
    error = result.get("error")

    if error:
        print(f"Checker message: {error}")

    if price is None:
        print("Price could not be detected.")
        return

    price = float(price)

    print(f"Current price: ₹{price}")
    print(f"Available: {available}")
    print(f"Price source: {source}")

    if (
        previous_price is None
        or price != float(previous_price)
    ):
        add_price_history(
            product_id=product_id,
            price=price,
            available=(
                True
                if available is None
                else available
            ),
        )

        print("Price history saved.")

    else:
        print(
            "Price unchanged. "
            "Duplicate history row skipped."
        )

    update_last_price(
        product_id=product_id,
        price=price,
    )

    print(
        "last_price updated in Supabase."
    )

    if previous_price is None:
        print(
            "This is the first recorded price."
        )

    else:
        previous_price = float(
            previous_price
        )

        if price < previous_price:
            price_drop = (
                previous_price - price
            )

            print(
                "Price dropped by "
                f"₹{price_drop:.2f}."
            )

        elif price > previous_price:
            price_increase = (
                price - previous_price
            )

            print(
                "Price increased by "
                f"₹{price_increase:.2f}."
            )

        else:
            print("Price has not changed.")

    if target_price is None:
        print("No target price set.")
        return

    target_price = float(target_price)

    if price <= target_price:
        print("TARGET PRICE REACHED!")

        alert_required = should_alert(
            current_price=price,
            target_price=target_price,
            last_alerted_price=(
                last_alerted_price
            ),
        )

        if alert_required:
            print("NEW ALERT REQUIRED.")

            try:
                send_telegram_alert(
                    telegram_id=telegram_id,
                    product_name=product_name,
                    website=website,
                    current_price=price,
                    target_price=target_price,
                    product_url=product_url,
                )

                print(
                    "Telegram alert sent."
                )

                update_last_alerted_price(
                    product_id=product_id,
                    price=price,
                )

                print(
                    "last_alerted_price "
                    "updated in Supabase."
                )

            except Exception as error:
                print(
                    "Telegram alert failed: "
                    f"{error}"
                )

                print(
                    "last_alerted_price was "
                    "NOT updated."
                )

        else:
            print(
                "No new alert required. "
                "Duplicate alert prevented."
            )

    else:
        difference = (
            price - target_price
        )

        print(
            "Target not reached. "
            f"Price is ₹{difference:.2f} "
            "above target."
        )


def run_price_checker():
    print(
        "Starting PriceWatch price checker..."
    )

    products = (
        get_all_active_products()
        or []
    )

    print(
        f"Found {len(products)} "
        "active product(s)."
    )

    if not products:
        print("No products to check.")
        return

    for product in products:
        try:
            process_product(product)

        except Exception as error:
            product_id = product.get(
                "id",
                "unknown",
            )

            print()
            print(
                "Unexpected error checking "
                f"product {product_id}: "
                f"{error}"
            )

    print()
    print("Price checking complete.")


if __name__ == "__main__":
    run_price_checker()