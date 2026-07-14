from checkers.generic import check_generic


def check_nakpro(product: dict) -> dict:
    result = check_generic(product)

    if result["price"] is not None:
        return result

    return {
        "price": None,
        "available": None,
        "source": "nakpro",
        "error": (
            "Nakpro price could not be found. "
            f"Generic checker error: {result['error']}"
        ),
    }