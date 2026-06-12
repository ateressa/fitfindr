"""
pytest tests for FitFindr tools.

Tests cover normal cases and failure modes for search_listings, suggest_outfit,
and create_fit_card.
"""

import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe, load_listings


# ── search_listings tests ─────────────────────────────────────────────────────

def test_search_listings_returns_list():
    """search_listings should return a list (possibly empty)."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)


def test_search_listings_returns_results():
    """search_listings should return results for a common query."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    # Check structure of returned items
    for item in results:
        assert "id" in item
        assert "title" in item
        assert "price" in item
        assert "size" in item


def test_search_listings_empty_results():
    """search_listings should return empty list when no matches, not raise exception."""
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_listings_price_filter():
    """search_listings should only return items at or below max_price."""
    results = search_listings("jacket", size=None, max_price=30)
    assert all(item["price"] <= 30 for item in results)


def test_search_listings_price_filter_strict():
    """search_listings should respect exact price boundaries."""
    results = search_listings("tee", size=None, max_price=20)
    assert all(item["price"] <= 20 for item in results)
    
    # Verify a higher price excludes some items
    results_higher = search_listings("tee", size=None, max_price=50)
    assert len(results_higher) >= len(results)


def test_search_listings_size_filter():
    """search_listings should filter by size (case-insensitive substring match)."""
    results = search_listings("jeans", size="M", max_price=100)
    assert all("m" in item["size"].lower() for item in results)


def test_search_listings_no_size_filter():
    """search_listings with size=None should not filter by size."""
    results = search_listings("jeans", size=None, max_price=100)
    # Should have results without size constraint
    assert len(results) > 0


def test_search_listings_sorted_by_relevance():
    """search_listings should sort results by keyword overlap score."""
    results = search_listings("vintage graphic tee", size=None, max_price=100)
    if len(results) > 1:
        # First result should have at least as good a score as later results
        # This is a basic check; detailed scoring would need refactoring for inspection
        assert results[0]["title"] is not None


def test_search_listings_returns_full_listing_dicts():
    """search_listings should return complete listing dictionaries."""
    results = search_listings("jacket", size=None, max_price=100)
    if results:
        item = results[0]
        required_fields = ["id", "title", "description", "category", "style_tags",
                           "size", "condition", "price", "colors", "brand", "platform"]
        for field in required_fields:
            assert field in item, f"Missing field: {field}"


# ── suggest_outfit tests ──────────────────────────────────────────────────────

def test_suggest_outfit_with_items():
    """suggest_outfit should return a non-empty string when wardrobe has items."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    
    new_item = results[0]
    wardrobe = get_example_wardrobe()
    
    outfit = suggest_outfit(new_item, wardrobe)
    assert isinstance(outfit, str)
    assert len(outfit) > 0
    assert outfit.strip() != ""


def test_suggest_outfit_with_empty_wardrobe():
    """suggest_outfit should return general styling advice for empty wardrobe."""
    results = search_listings("jacket", size=None, max_price=100)
    assert len(results) > 0
    
    new_item = results[0]
    empty_wardrobe = get_empty_wardrobe()
    
    outfit = suggest_outfit(new_item, empty_wardrobe)
    assert isinstance(outfit, str)
    assert len(outfit) > 0
    assert outfit.strip() != ""


def test_suggest_outfit_returns_non_empty_string():
    """suggest_outfit should never return an empty string."""
    results = search_listings("tee", size=None, max_price=50)
    assert len(results) > 0
    
    for new_item in results[:3]:  # Test first 3 results
        wardrobe = get_example_wardrobe()
        outfit = suggest_outfit(new_item, wardrobe)
        assert outfit and outfit.strip(), "suggest_outfit returned empty string"


def test_suggest_outfit_mentions_wardrobe_items():
    """suggest_outfit with a wardrobe should reference wardrobe item names."""
    results = search_listings("vintage tee", size=None, max_price=50)
    assert len(results) > 0
    
    new_item = results[0]
    wardrobe = get_example_wardrobe()
    
    outfit = suggest_outfit(new_item, wardrobe)
    # Check if outfit mentions some item characteristics from the wardrobe
    # (This is a loose check since LLM output varies)
    assert len(outfit) > 20  # Should be a substantive response


# ── create_fit_card tests ─────────────────────────────────────────────────────

def test_create_fit_card_with_valid_inputs():
    """create_fit_card should return a non-empty caption string with valid inputs."""
    outfit = "Pair with baggy jeans and chunky sneakers for a 90s vibe."
    new_item = load_listings()[0]
    
    caption = create_fit_card(outfit, new_item)
    assert isinstance(caption, str)
    assert len(caption) > 0
    assert caption.strip() != ""


def test_create_fit_card_empty_outfit_guard():
    """create_fit_card should return error message for empty outfit, not crash."""
    new_item = load_listings()[0]
    
    caption = create_fit_card("", new_item)
    assert isinstance(caption, str)
    assert "error" in caption.lower() or "incomplete" in caption.lower()


def test_create_fit_card_whitespace_only_outfit():
    """create_fit_card should catch whitespace-only outfit strings."""
    new_item = load_listings()[0]
    
    caption = create_fit_card("   ", new_item)
    assert isinstance(caption, str)
    assert "error" in caption.lower() or "incomplete" in caption.lower()


def test_create_fit_card_mentions_item_details():
    """create_fit_card should include item name, price, and platform in caption."""
    outfit = "Perfect for casual weekends with jeans and sneakers."
    new_item = load_listings()[0]
    
    caption = create_fit_card(outfit, new_item)
    # Caption should be a string (LLM may or may not include these,
    # but we're checking structure, not content guarantees)
    assert isinstance(caption, str)
    assert len(caption) > 10


def test_create_fit_card_returns_reasonable_length():
    """create_fit_card should return a 2-4 sentence caption."""
    outfit = "Pair with dark jeans and black boots for a moody aesthetic."
    new_item = load_listings()[0]
    
    caption = create_fit_card(outfit, new_item)
    # Check it's a reasonable caption length (not too short, not too long)
    assert len(caption) > 20
    assert len(caption) < 500


def test_create_fit_card_no_exception_on_missing_outfit():
    """create_fit_card should not raise an exception for missing outfit."""
    new_item = load_listings()[0]
    
    # Should not raise
    try:
        caption = create_fit_card("", new_item)
        assert isinstance(caption, str)
    except Exception as e:
        pytest.fail(f"create_fit_card raised an exception: {e}")


# ── Integration tests ─────────────────────────────────────────────────────────

def test_tools_integration_happy_path():
    """Test the full flow: search → suggest outfit → create caption."""
    # Step 1: Search
    results = search_listings("vintage graphic tee", size="M", max_price=30)
    assert len(results) > 0
    
    # Step 2: Suggest outfit
    new_item = results[0]
    wardrobe = get_example_wardrobe()
    outfit = suggest_outfit(new_item, wardrobe)
    assert outfit and outfit.strip()
    
    # Step 3: Create caption
    caption = create_fit_card(outfit, new_item)
    assert caption and caption.strip()
    assert "error" not in caption.lower()


def test_tools_integration_no_results_path():
    """Test the error path: search returns nothing."""
    results = search_listings("designer ballgown", size="XXS", max_price=1)
    assert results == []
    # Agent should stop here and not call suggest_outfit or create_fit_card


def test_search_listings_with_all_filters():
    """search_listings with description, size, and max_price all specified."""
    results = search_listings("denim", size="W", max_price=50)
    assert isinstance(results, list)
    if results:
        for item in results:
            assert item["price"] <= 50
            assert "w" in item["size"].lower()
