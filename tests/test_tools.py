from utils.data_loader import get_empty_wardrobe, get_example_wardrobe
from tools import create_fit_card, search_listings, suggest_outfit


def _sample_item() -> dict:
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    return results[0]


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)

    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)

    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)

    assert all(item["price"] <= 10 for item in results)


def test_search_does_not_confuse_shoe_size_with_waist_size():
    results = search_listings("black combat boots", size="8", max_price=None)

    assert results == []


def test_suggest_outfit_with_example_wardrobe():
    outfit = suggest_outfit(_sample_item(), get_example_wardrobe())

    assert isinstance(outfit, str)
    assert outfit.strip()


def test_suggest_outfit_with_empty_wardrobe():
    outfit = suggest_outfit(_sample_item(), get_empty_wardrobe())

    assert isinstance(outfit, str)
    assert outfit.strip()


def test_create_fit_card_returns_caption():
    item = _sample_item()
    outfit = (
        "Pair it with baggy straight-leg jeans, chunky white sneakers, and a "
        "black crossbody bag for a relaxed thrifted streetwear look."
    )

    caption = create_fit_card(outfit, item)

    assert isinstance(caption, str)
    assert caption.strip()
    assert caption != "Cannot create a fit card without an outfit suggestion."


def test_create_fit_card_empty_outfit():
    item = _sample_item()

    caption = create_fit_card("   ", item)

    assert caption == "Cannot create a fit card without an outfit suggestion."
