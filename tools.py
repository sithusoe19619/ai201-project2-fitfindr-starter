"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _chat_completion(prompt: str, temperature: float = 0.7) -> str:
    """Call Groq and return the assistant's message text."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are FitFindr, a practical secondhand fashion stylist. "
                    "Give concise, specific, wearable advice."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


def _tokenize(text: str) -> set[str]:
    """Normalize text into searchable lowercase word tokens."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _listing_search_text(listing: dict) -> str:
    """Combine searchable fields from one listing into a single string."""
    values = [
        listing.get("title"),
        listing.get("description"),
        listing.get("category"),
        listing.get("size"),
        listing.get("condition"),
        listing.get("brand"),
        listing.get("platform"),
        " ".join(listing.get("style_tags") or []),
        " ".join(listing.get("colors") or []),
    ]
    return " ".join(str(value) for value in values if value)


def _size_matches(requested_size: str, listing_size: str) -> bool:
    """Match clothing and shoe sizes without substring false positives."""
    requested = requested_size.strip().lower()
    available = listing_size.strip().lower()

    requested_numbers = re.findall(r"\d+(?:\.\d+)?", requested)
    if requested_numbers:
        available_numbers = re.findall(r"\d+(?:\.\d+)?", available)
        return requested_numbers == available_numbers

    requested_tokens = _tokenize(requested)
    available_tokens = _tokenize(available)
    return requested_tokens.issubset(available_tokens)


def _matches_requested_item_type(query_tokens: set[str], listing: dict) -> bool:
    """Prevent a color-only match from returning the wrong kind of item."""
    item_type_groups = [
        {"tee", "shirt", "top"},
        {"hoodie", "sweatshirt", "crewneck"},
        {"jeans", "pants", "trousers", "bottoms"},
        {"shorts"},
        {"skirt"},
        {"dress"},
        {"jacket", "blazer", "bomber", "windbreaker", "outerwear"},
        {"boots", "boot"},
        {"sneakers", "shoes", "shoe"},
        {"belt"},
        {"bag"},
        {"hat"},
        {"cardigan"},
        {"vest"},
    ]
    listing_tokens = _tokenize(_listing_search_text(listing))

    for group in item_type_groups:
        requested_types = query_tokens & group
        if requested_types and not listing_tokens.intersection(group):
            return False
    return True


def _format_listing(item: dict) -> str:
    """Format a listing for an LLM prompt."""
    return (
        f"Title: {item.get('title', 'Unknown item')}\n"
        f"Category: {item.get('category', 'unknown')}\n"
        f"Style tags: {', '.join(item.get('style_tags') or [])}\n"
        f"Size: {item.get('size', 'unknown')}\n"
        f"Condition: {item.get('condition', 'unknown')}\n"
        f"Price: ${item.get('price', 'unknown')}\n"
        f"Colors: {', '.join(item.get('colors') or [])}\n"
        f"Brand: {item.get('brand') or 'unbranded'}\n"
        f"Platform: {item.get('platform', 'unknown')}"
    )


def _format_wardrobe_items(items: list[dict]) -> str:
    """Format wardrobe items for an LLM prompt."""
    lines = []
    for item in items:
        notes = item.get("notes") or "no notes"
        lines.append(
            "- "
            f"{item.get('name', 'Unnamed item')} "
            f"({item.get('category', 'unknown')}; "
            f"colors: {', '.join(item.get('colors') or [])}; "
            f"style tags: {', '.join(item.get('style_tags') or [])}; "
            f"notes: {notes})"
        )
    return "\n".join(lines)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    query_tokens = _tokenize(description or "")
    if not query_tokens:
        return []

    scored_listings = []
    requested_size = size.strip().lower() if size else None

    for listing in load_listings():
        if max_price is not None and listing["price"] > max_price:
            continue

        listing_size = str(listing.get("size", ""))
        if requested_size and not _size_matches(requested_size, listing_size):
            continue

        if not _matches_requested_item_type(query_tokens, listing):
            continue

        search_text = _listing_search_text(listing)
        listing_tokens = _tokenize(search_text)
        overlap = query_tokens & listing_tokens
        if not overlap:
            continue

        score = len(overlap)
        if (description or "").lower() in search_text.lower():
            score += 2

        scored_listings.append((score, listing["price"], listing))

    scored_listings.sort(key=lambda item: (-item[0], item[1]))
    return [listing for _, _, listing in scored_listings]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    wardrobe_items = wardrobe.get("items", []) if wardrobe else []
    item_details = _format_listing(new_item or {})

    if not wardrobe_items:
        prompt = f"""
Suggest 1-2 complete outfits for this secondhand item.

New item:
{item_details}

The user has not added wardrobe items yet, so give general styling advice.
Mention what kinds of bottoms, shoes, layers, and accessories would pair well.
Format the response as:
**Look 1 — short vibe name**
- One concise outfit description.
**Look 2 — short vibe name**
- One concise outfit description.
Keep the full response under 110 words.
"""
        return _chat_completion(prompt, temperature=0.7)

    prompt = f"""
Suggest 1-2 complete outfits using this secondhand item and named pieces from
the user's wardrobe.

New item:
{item_details}

User wardrobe:
{_format_wardrobe_items(wardrobe_items)}

Use specific wardrobe item names where they fit. Include practical styling
details like layers, shoes, proportions, or accessories.
Format the response as:
**Look 1 — short vibe name**
- One concise outfit description.
**Look 2 — short vibe name**
- One concise outfit description.
Keep the full response under 120 words.
"""
    return _chat_completion(prompt, temperature=0.7)


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Cannot create a fit card without an outfit suggestion."

    prompt = f"""
Create a short social outfit caption for this thrifted find.

New item:
{_format_listing(new_item or {})}

Outfit idea:
{outfit.strip()}

Requirements:
- 2-3 sentences and no more than 80 words.
- Casual and authentic, like a real OOTD caption.
- Mention the item title, price, and platform naturally once each.
- Capture the outfit vibe in specific terms.
- Do not use hashtags unless they feel natural.
"""
    return _chat_completion(prompt, temperature=1.0).strip('"')
