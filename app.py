import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from database import add_product, get_products, remove_product
from price_checker import check_product

# Load environment variables from .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")


# Conversation states
WEBSITE, PRODUCT_URL, PRODUCT_NAME, TARGET_PRICE, PINCODE = range(5)


WEBSITES = {
    "1": "Amul",
    "2": "Nakpro",
    "3": "Nutrabay",
    "4": "Amazon India",
    "5": "Flipkart",
    "6": "HyugaLife",
    "7": "HealthKart",
    "8": "MuscleBlaze",
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to PriceWatch!\n\n"
        "I track product prices and notify you when they reach your target.\n\n"
        "Use /help to see the available commands."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 PriceWatch Help\n\n"
        "➕ /add - Add a product to track\n"
        "📋 /list - View tracked products\n"
        "❌ /remove <ID> - Stop tracking a product\n"
        "🔍 /check - Check prices now\n"
        "⚙️ /settings - View settings\n"
        "❓ /help - Show this guide\n\n"
        "How to add a product:\n"
        "1️⃣ Type /add\n"
        "2️⃣ Choose the website\n"
        "3️⃣ Send the product link\n"
        "4️⃣ Enter the product name\n"
        "5️⃣ Enter your target price\n"
        "6️⃣ Enter your delivery pincode or type /skip\n\n"
        "Example:\n"
        "/add\n"
        "4\n"
        "https://www.amazon.in/...\n"
        "Nakpro Whey Platinum 1kg\n"
        "1500\n"
        "842001"
    )


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    website_text = "\n".join(
        f"{number}. {website}"
        for number, website in WEBSITES.items()
    )

    await update.message.reply_text(
        "🛒 Choose the website:\n\n"
        f"{website_text}\n\n"
        "Send the corresponding number.\n\n"
        "Type /cancel to cancel."
    )

    return WEBSITE


async def receive_website(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    choice = update.message.text.strip()

    if choice not in WEBSITES:
        await update.message.reply_text(
            "❌ Invalid option.\n\n"
            "Please send a number from 1 to 8."
        )
        return WEBSITE

    context.user_data["website"] = WEBSITES[choice]

    await update.message.reply_text(
        f"✅ Website: {WEBSITES[choice]}\n\n"
        "🔗 Now send the product link."
    )

    return PRODUCT_URL


async def receive_url(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    product_url = update.message.text.strip()

    if not product_url.startswith(("http://", "https://")):
        await update.message.reply_text(
            "❌ That does not look like a valid link.\n\n"
            "Please send the full product URL."
        )
        return PRODUCT_URL

    context.user_data["product_url"] = product_url

    await update.message.reply_text(
        "📦 Enter a name for this product.\n\n"
        "Example:\n"
        "Nakpro Whey Platinum 1kg"
    )

    return PRODUCT_NAME


async def receive_product_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    product_name = update.message.text.strip()

    if not product_name:
        await update.message.reply_text(
            "❌ Product name cannot be empty."
        )
        return PRODUCT_NAME

    context.user_data["product_name"] = product_name

    await update.message.reply_text(
        "💰 Enter your target price in ₹.\n\n"
        "Example:\n"
        "1500"
    )

    return TARGET_PRICE


async def receive_target_price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    price_text = update.message.text.strip().replace(",", "")

    try:
        target_price = float(price_text)

        if target_price <= 0:
            raise ValueError

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid price.\n\n"
            "Please enter a number such as:\n"
            "1500"
        )
        return TARGET_PRICE

    context.user_data["target_price"] = target_price

    await update.message.reply_text(
        "📍 Enter your 6-digit delivery pincode.\n\n"
        "This may be useful for Amazon, Amazon Fresh, "
        "Flipkart and other location-dependent stores.\n\n"
        "If pincode is not needed, type /skip."
    )

    return PINCODE


async def receive_pincode(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    pincode = update.message.text.strip()

    if not pincode.isdigit() or len(pincode) != 6:
        await update.message.reply_text(
            "❌ Please enter a valid 6-digit Indian pincode.\n\n"
            "Or type /skip."
        )
        return PINCODE

    return await save_product(
        update,
        context,
        pincode,
    )


async def skip_pincode(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    return await save_product(
        update,
        context,
        None,
    )


async def save_product(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    pincode,
):
    telegram_id = update.effective_user.id

    try:
        add_product(
            telegram_id=telegram_id,
            product_name=context.user_data["product_name"],
            website=context.user_data["website"],
            product_url=context.user_data["product_url"],
            target_price=context.user_data["target_price"],
            pincode=pincode,
        )

        product_name = context.user_data["product_name"]
        website = context.user_data["website"]
        target_price = context.user_data["target_price"]

        pincode_text = pincode if pincode else "Not specified"

        await update.message.reply_text(
            "✅ Product added to PriceWatch!\n\n"
            f"📦 {product_name}\n"
            f"🛒 Website: {website}\n"
            f"🎯 Target price: ₹{target_price:g}\n"
            f"📍 Pincode: {pincode_text}\n\n"
            "💾 Saved to the PriceWatch database."
        )

        context.user_data.clear()

        return ConversationHandler.END

    except Exception as error:
        print(f"Database error: {error}")

        await update.message.reply_text(
            "❌ I could not save the product.\n\n"
            "Please try again later."
        )

        return ConversationHandler.END


async def list_products(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    telegram_id = update.effective_user.id

    try:
        response = get_products(telegram_id)
        products = response.data

        if not products:
            await update.message.reply_text(
                "📭 You are not tracking any products yet.\n\n"
                "Use /add to add one."
            )
            return

        message = "📋 Your tracked products\n\n"

        for product in products:
            target_price = product["target_price"]

            message += (
                f"🆔 ID: {product['id']}\n"
                f"📦 {product['product_name']}\n"
                f"🛒 {product['website']}\n"
                f"🎯 Target: ₹{target_price}\n"
            )

            if product.get("last_price") is not None:
                message += (
                    f"💵 Last price: ₹{product['last_price']}\n"
                )

            if product.get("pincode"):
                message += (
                    f"📍 Pincode: {product['pincode']}\n"
                )

            message += (
                f"🔗 {product['product_url']}\n\n"
            )

        await update.message.reply_text(
            message,
            disable_web_page_preview=True,
        )

    except Exception as error:
        print(f"Database error: {error}")

        await update.message.reply_text(
            "❌ I could not load your tracked products."
        )


async def remove_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    telegram_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "❌ Please provide the product ID.\n\n"
            "Example:\n"
            "/remove 3\n\n"
            "Use /list to see product IDs."
        )
        return

    try:
        product_id = int(context.args[0])

    except ValueError:
        await update.message.reply_text(
            "❌ Product ID must be a number."
        )
        return

    try:
        response = remove_product(
            product_id,
            telegram_id,
        )

        if not response.data:
            await update.message.reply_text(
                "❌ Product not found.\n\n"
                "Use /list to check your tracked products."
            )
            return

        await update.message.reply_text(
            f"🛑 Product {product_id} is no longer being tracked."
        )

    except Exception as error:
        print(f"Database error: {error}")

        await update.message.reply_text(
            "❌ I could not remove the product."
        )


async def check_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    telegram_id = update.effective_user.id

    await update.message.reply_text(
        "🔍 Checking your tracked products..."
    )

    try:
        response = get_products(telegram_id)
        products = response.data

        if not products:
            await update.message.reply_text(
                "📭 You are not tracking any products yet.\n\n"
                "Use /add to add one."
            )
            return

        results = []

        for product in products:
            product_name = product.get(
                "product_name",
                "Unknown product",
            )

            website = product.get(
                "website",
                "Unknown website",
            )

            target_price = product.get("target_price")
            product_url = product.get("product_url", "")

            try:
                result = check_product(product)

                price = result.get("price")
                available = result.get("available")
                error = result.get("error")

                if price is None:
                    error_text = (
                        error
                        or "Price could not be detected."
                    )

                    results.append(
                        f"📦 {product_name}\n"
                        f"🛒 {website}\n"
                        f"⚠️ {error_text}"
                    )

                    continue

                price = float(price)

                message = (
                    f"📦 {product_name}\n"
                    f"🛒 {website}\n"
                    f"💰 Current price: ₹{price:g}\n"
                )

                if target_price is not None:
                    target_price = float(target_price)

                    message += (
                        f"🎯 Target: ₹{target_price:g}\n"
                    )

                    if price <= target_price:
                        message += (
                            "🔥 TARGET PRICE REACHED!\n"
                        )

                    else:
                        difference = price - target_price

                        message += (
                            f"📈 ₹{difference:g} above target\n"
                        )

                if available is False:
                    message += "❌ Currently unavailable\n"

                message += f"🔗 {product_url}"

                results.append(message)

            except Exception as error:
                print(
                    "Manual check error for product "
                    f"{product.get('id')}: {error}"
                )

                results.append(
                    f"📦 {product_name}\n"
                    "❌ Could not check this product."
                )

        final_message = (
            f"🔍 Checked {len(products)} tracked "
            f"product(s)\n\n"
            + "\n\n".join(results)
            + "\n\n✅ Price check complete."
        )

        await update.message.reply_text(
            final_message,
            disable_web_page_preview=True,
        )

    except Exception as error:
        print(f"Manual price check error: {error}")

        await update.message.reply_text(
            "❌ I could not check prices right now.\n\n"
            "Please try again later."
        )

async def settings_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "⚙️ PriceWatch Settings\n\n"
        "⏱ Planned check interval: 15 minutes\n"
        "🔔 Price alerts: Enabled\n"
        "📍 Pincode tracking: Supported where applicable"
    )


async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.clear()

    await update.message.reply_text(
        "❌ Product addition cancelled."
    )

    return ConversationHandler.END


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing.")

    app = Application.builder().token(BOT_TOKEN).build()

    add_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_start),
        ],
        states={
            WEBSITE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_website,
                )
            ],
            PRODUCT_URL: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_url,
                )
            ],
            PRODUCT_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_product_name,
                )
            ],
            TARGET_PRICE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_target_price,
                )
            ],
            PINCODE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_pincode,
                ),
                CommandHandler(
                    "skip",
                    skip_pincode,
                ),
            ],
        },
        fallbacks=[
            CommandHandler(
                "cancel",
                cancel,
            )
        ],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(add_conversation)

    app.add_handler(CommandHandler("list", list_products))
    app.add_handler(CommandHandler("remove", remove_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("settings", settings_command))

    port = int(os.environ.get("PORT", 10000))
    render_external_url = os.environ.get("RENDER_EXTERNAL_URL")

    if render_external_url:
        webhook_url = f"{render_external_url}/telegram"

        print("PriceWatch is starting in webhook mode...")
        print(f"Webhook URL: {webhook_url}")

        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="telegram",
            webhook_url=webhook_url,
        )

    else:
        print("PriceWatch is running locally in polling mode...")

        app.run_polling()


if __name__ == "__main__":
    main()