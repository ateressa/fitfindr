"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


def _parse_query(query: str) -> dict:
    """Extract search filters from the user's natural-language query."""
    parsed_query = query.strip()
    size = None
    max_price = None

    price_patterns = [
        r"\b(?:under|below|less than|up to|max(?:imum)?)\s*\$?(\d+(?:\.\d+)?)\b",
        r"\b\$?(\d+(?:\.\d+)?)\s*or less\b",
        r"\b<=\s*\$?(\d+(?:\.\d+)?)\b",
    ]
    for pattern in price_patterns:
        match = re.search(pattern, parsed_query, flags=re.IGNORECASE)
        if match:
            max_price = float(match.group(1))
            parsed_query = re.sub(pattern, "", parsed_query, count=1, flags=re.IGNORECASE)
            break

    size_match = re.search(r"\bsize\b", parsed_query, flags=re.IGNORECASE)
    if size_match:
        size_start = size_match.start()
        tail = parsed_query[size_match.end():].strip()
        tail_tokens = tail.split()
        if tail_tokens:
            candidate_tokens = []
            consumed = 0
            for token in tail_tokens:
                normalized = token.strip(",;:")
                if not normalized:
                    consumed += 1
                    continue
                if candidate_tokens and not any(ch.isdigit() for ch in normalized) and "/" not in normalized and "-" not in normalized and not re.fullmatch(r"[A-Z]", normalized):
                    break
                candidate_tokens.append(normalized)
                consumed += 1
                if len(candidate_tokens) >= 3:
                    break

            if candidate_tokens:
                size = " ".join(candidate_tokens)
                prefix = parsed_query[:size_start]
                suffix = " ".join(tail_tokens[consumed:])
                parsed_query = f"{prefix} {suffix}".strip()

    description = re.sub(r"[\s,;:]+", " ", parsed_query).strip()
    if not description:
        description = ""

    return {
        "description": description,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    session = _new_session(query, wardrobe)

    session["parsed"] = _parse_query(query)

    session["search_results"] = search_listings(
        session["parsed"]["description"],
        size=session["parsed"]["size"],
        max_price=session["parsed"]["max_price"],
    )
    if not session["search_results"]:
        description = session["parsed"]["description"]
        size = session["parsed"]["size"]
        max_price = session["parsed"]["max_price"]
        size_text = f" size {size}" if size else ""
        price_text = f" under ${max_price:g}" if max_price is not None else ""
        session["error"] = (
            f"Sorry, I couldn't find any listings matching {description}{size_text}{price_text}. "
            "Try a different description, skip the size filter, or increase your budget."
        )
        return session

    session["selected_item"] = session["search_results"][0]

    try:
        session["outfit_suggestion"] = suggest_outfit(
            session["selected_item"],
            wardrobe,
        )
    except Exception as exc:  # pragma: no cover - defensive tool boundary
        session["error"] = f"Could not generate outfit suggestions: {exc}"
        return session

    if not session["outfit_suggestion"] or not session["outfit_suggestion"].strip():
        session["error"] = "Could not generate outfit suggestions because the response was empty."
        return session

    try:
        session["fit_card"] = create_fit_card(
            session["outfit_suggestion"],
            session["selected_item"],
        )
    except Exception as exc:  # pragma: no cover - defensive tool boundary
        session["error"] = f"Could not generate fit card: {exc}"
        return session

    if not session["fit_card"] or not session["fit_card"].strip():
        session["error"] = "Could not generate fit card because the response was empty."
        return session

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
