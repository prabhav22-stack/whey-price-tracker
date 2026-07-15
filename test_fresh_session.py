from playwright.sync_api import sync_playwright
import json


SEARCH_TERM = "nakpro whey platinum"

FRESH_PAGE = (
    "https://www.amazon.in/tez/browse/search"
    "?qcbrand=ctnow"
)

API_URL = (
    "https://www.amazon.in/tez/browse/searchByKeyword"
    "?keyword=nakpro%20whey%20platinum"
    "&brandId=ctnow"
    "&offset=0"
    "&spellCorrectionDisabled=false"
    "&sortOption=relevanceblender"
    "&searchSource=search"
)


with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False
    )

    context = browser.new_context(
        locale="en-IN"
    )

    page = context.new_page()

    # ---------------------------------------------------------
    # STEP 1: OPEN AMAZON HOMEPAGE
    # ---------------------------------------------------------

    print("Opening Amazon homepage...")

    try:
        page.goto(
            "https://www.amazon.in/",
            wait_until="domcontentloaded",
            timeout=60000,
        )

    except Exception as error:
        print("Homepage navigation raised:", type(error).__name__)
        print("Homepage error:", str(error)[:500])

    page.wait_for_timeout(3000)

    print("Homepage URL:", page.url)

    try:
        print("Homepage title:", page.title())
    except Exception as error:
        print("Could not read homepage title:", error)

    # ---------------------------------------------------------
    # STEP 2: HANDLE AMAZON CONTINUE SHOPPING PAGE
    # ---------------------------------------------------------

    try:
        continue_button = page.get_by_text(
            "Continue shopping",
            exact=False,
        )

        if continue_button.count() > 0:
            print("Amazon Continue Shopping page detected.")
            print("Clicking Continue shopping...")

            continue_button.first.click()

            page.wait_for_timeout(5000)

            print(
                "URL after Continue Shopping:",
                page.url,
            )

    except Exception as error:
        print(
            "Continue Shopping handling raised:",
            type(error).__name__,
        )

        print(
            "Continue Shopping error:",
            str(error)[:500],
        )

    # ---------------------------------------------------------
    # STEP 3: OPEN AMAZON FRESH LANDING PAGE
    # ---------------------------------------------------------

    print("\nOpening Fresh landing page...")

    try:
        page.goto(
            FRESH_PAGE,
            wait_until="commit",
            timeout=60000,
        )

    except Exception as error:
        print(
            "Fresh navigation raised:",
            type(error).__name__,
        )

        print(
            "Navigation error:",
            str(error)[:500],
        )

    # Do not crash after ERR_ABORTED.
    # Give Amazon time to complete redirects or page changes.

    page.wait_for_timeout(5000)

    print("Fresh page URL:", page.url)

    try:
        print("Fresh page title:", page.title())

    except Exception as error:
        print(
            "Could not read Fresh page title:",
            error,
        )

    # ---------------------------------------------------------
    # STEP 4: DISPLAY COOKIE NAMES ONLY
    # ---------------------------------------------------------

    print("\nBrowser cookie names:")

    try:
        cookies = context.cookies()

        if not cookies:
            print("No cookies found.")

        for cookie in cookies:
            # SECURITY:
            # Print names only. Never print cookie values.
            print("-", cookie["name"])

    except Exception as error:
        print(
            "Cookie inspection error:",
            str(error)[:500],
        )

    # ---------------------------------------------------------
    # STEP 5: CALL FRESH API FROM THE CURRENT PAGE
    # ---------------------------------------------------------

    print("\nCalling Fresh API inside browser...")

    try:
        result = page.evaluate(
            """
            async (url) => {
                try {
                    const response = await fetch(url, {
                        method: "GET",
                        credentials: "include"
                    });

                    const text = await response.text();

                    return {
                        ok: true,
                        status: response.status,
                        contentType:
                            response.headers.get("content-type"),
                        length: text.length,
                        text: text
                    };

                } catch (error) {
                    return {
                        ok: false,
                        error: String(error)
                    };
                }
            }
            """,
            API_URL,
        )

    except Exception as error:
        print(
            "Browser API execution failed:",
            type(error).__name__,
        )

        print(
            "Execution error:",
            str(error)[:1000],
        )

        result = None

    # ---------------------------------------------------------
    # STEP 6: INSPECT API RESULT
    # ---------------------------------------------------------

    if result is None:
        print("\nNo API result returned.")

    elif not result.get("ok"):
        print("\nFetch failed inside browser.")

        print(
            "Fetch error:",
            result.get("error"),
        )

    else:
        print(
            "Status:",
            result["status"],
        )

        print(
            "Content-Type:",
            result["contentType"],
        )

        print(
            "Response length:",
            result["length"],
        )

        print("\nResponse preview:")

        print(
            result["text"][:2000]
        )

        # -----------------------------------------------------
        # STEP 7: SAVE VALID JSON RESPONSE
        # -----------------------------------------------------

        if result["text"]:
            try:
                data = json.loads(
                    result["text"]
                )

                with open(
                    "fresh_response.json",
                    "w",
                    encoding="utf-8",
                ) as file:
                    json.dump(
                        data,
                        file,
                        indent=2,
                        ensure_ascii=False,
                    )

                print(
                    "\nSaved JSON to fresh_response.json"
                )

            except json.JSONDecodeError:
                print(
                    "\nResponse was not valid JSON."
                )

    # ---------------------------------------------------------
    # KEEP BROWSER OPEN FOR MANUAL INSPECTION
    # ---------------------------------------------------------

    input(
        "\nPress Enter to close browser..."
    )

    browser.close()