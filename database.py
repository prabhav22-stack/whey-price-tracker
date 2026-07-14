import os

from dotenv import load_dotenv
from supabase import Client, create_client


load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL is missing from .env")

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY is missing from .env")


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


def add_product(
    telegram_id,
    product_name,
    website,
    product_url,
    target_price,
    pincode=None,
):
    data = {
        "telegram_id": str(telegram_id),
        "product_name": product_name,
        "website": website,
        "product_url": product_url,
        "target_price": float(target_price),
        "pincode": pincode,
        "active": True,
    }

    return (
        supabase.table("tracked_products")
        .insert(data)
        .execute()
    )


def get_products(telegram_id):
    return (
        supabase.table("tracked_products")
        .select("*")
        .eq("telegram_id", str(telegram_id))
        .eq("active", True)
        .execute()
    )


def get_all_active_products():
    response = (
        supabase.table("tracked_products")
        .select("*")
        .eq("active", True)
        .execute()
    )

    return response.data


def remove_product(product_id, telegram_id):
    return (
        supabase.table("tracked_products")
        .update(
            {
                "active": False,
            }
        )
        .eq("id", product_id)
        .eq("telegram_id", str(telegram_id))
        .execute()
    )


def update_last_price(product_id, price):
    return (
        supabase.table("tracked_products")
        .update(
            {
                "last_price": float(price),
            }
        )
        .eq("id", product_id)
        .execute()
    )


def add_price_history(
    product_id,
    price,
    available=True,
):
    data = {
        "product_id": product_id,
        "price": float(price),
        "available": bool(available),
    }

    return (
        supabase.table("price_history")
        .insert(data)
        .execute()
    )


def update_last_alerted_price(
    product_id,
    price,
):
    return (
        supabase.table("tracked_products")
        .update(
            {
                "last_alerted_price": float(price),
            }
        )
        .eq("id", product_id)
        .execute()
    )


def get_product(product_id):
    response = (
        supabase.table("tracked_products")
        .select("*")
        .eq("id", product_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]