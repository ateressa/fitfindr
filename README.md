# FitFindr

FitFindr is a small agent app that searches mock secondhand listings, suggests an outfit using the user's wardrobe, and turns the result into a caption-style fit card.

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Groq API key:

```text
GROQ_API_KEY=your_key_here
```

Run the app with:

```bash
python app.py
```

## Project Files

- `app.py`: Gradio UI and query handler.
- `agent.py`: Planning loop and session state orchestration.
- `tools.py`: The three required tools.
- `planning.md`: Design spec, loop description, and architecture.
- `utils/data_loader.py`: Helpers for loading listings and wardrobe data.

## Tool Inventory

| Tool | Inputs | Outputs | Purpose |
|---|---|---|---|
| `search_listings` | `description: str`, `size: str \| None`, `max_price: float \| None` | `list[dict]` of matching listings | Filters the mock listings dataset and returns the best-ranked matches for the user's request. |
| `suggest_outfit` | `new_item: dict`, `wardrobe: dict` | `str` outfit suggestion | Generates styling guidance for the selected listing using the user's wardrobe, or general styling advice if the wardrobe is empty. |
| `create_fit_card` | `outfit: str`, `new_item: dict` | `str` fit-card caption | Converts the outfit suggestion into a short social-media-style caption that mentions the item, price, and platform. |

## Planning Loop

The agent follows a straight-through pipeline with one early-exit branch:

1. Create a fresh session with `_new_session(query, wardrobe)`.
2. Parse the query into `session["parsed"]` with `description`, `size`, and `max_price`.
3. Call `search_listings()` with the parsed values.
4. Store the returned list in `session["search_results"]`.
5. If the list is empty, set `session["error"]` and return immediately.
6. Otherwise, set `session["selected_item"]` to the first result.
7. Call `suggest_outfit(session["selected_item"], wardrobe)` and store the string in `session["outfit_suggestion"]`.
8. If the outfit string is blank, set `session["error"]` and return early.
9. Call `create_fit_card(session["outfit_suggestion"], session["selected_item"])` and store the result in `session["fit_card"]`.
10. Return the completed session.

This is intentionally not a free-form agent loop. The output of each step becomes the input to the next step, and the empty-search branch stops the chain before any styling or caption generation happens.

## State Management

All intermediate results live in one session dictionary. That session is created once and updated in place so each tool can read the previous tool's output.

The session tracks these keys:

- `query`: original user input.
- `parsed`: extracted `description`, `size`, and `max_price` values.
- `search_results`: list returned by `search_listings()`.
- `selected_item`: first search result, passed to the next tools.
- `wardrobe`: wardrobe dict selected by the UI.
- `outfit_suggestion`: string returned by `suggest_outfit()`.
- `fit_card`: string returned by `create_fit_card()`.
- `error`: `None` on success, otherwise a human-readable early-exit message.

That structure made it easy to validate state flow during testing. In the walkthrough query from `planning.md`, the exact dict stored in `session["selected_item"]` was the same object passed into `suggest_outfit()`, and the resulting `session["outfit_suggestion"]` was then passed unchanged into `create_fit_card()`.

## Error Handling

| Tool | Failure mode | Response |
|---|---|---|
| `search_listings` | No matching listings | Set `session["error"]` and return immediately without calling the styling or caption tools. Concrete example: `designer ballgown size XXS under $5` returned an error and left `session["fit_card"]` as `None`. |
| `suggest_outfit` | Empty or unusable outfit text | Set `session["error"]` and return early. The agent does not try to caption a blank outfit. |
| `create_fit_card` | Blank outfit input | Return a descriptive error string instead of calling the LLM. |

Concrete test result from the no-results branch:

```text
SESSION_ERROR: Sorry, I couldn't find any listings matching designer ballgown size XXS under $5. Try a different description, skip the size filter, or increase your budget.
SESSION_FIT_CARD: None
CALL_COUNTS: {'search': 1, 'outfit': 0, 'card': 0}
```

That confirmed `suggest_outfit()` and `create_fit_card()` were not called after an empty search.

## Spec Reflection

The implementation follows the spec closely: the planning loop is deterministic, state is carried through a single session dict, and each tool has a clear failure boundary. The query parser in `agent.py` strips size and price phrases before searching, which matches the intended planning behavior for inputs like `vintage graphic tee under $30`.

The main tradeoff is that the query parser is rule-based rather than LLM-based. That keeps the loop predictable and easy to test, but it means some unusually phrased queries may need extra handling later. The current version is a good fit for this milestone because the required behavior is branching on tool output, not open-ended natural-language interpretation.

## AI Usage

I used an AI assistant in two specific places while building this project:

1. I gave the assistant the `Planning Loop`, `State Management`, and `Architecture` sections from `planning.md`, along with the current `agent.py` skeleton, and asked it to review whether the implementation actually branched on `search_listings()` output. It produced a review that confirmed the session-based pipeline was mostly correct and flagged one parser edge case: a fallback path that could reintroduce size and price text into `session["parsed"]["description"]`. I changed the parser to keep the description empty instead of restoring the original query, which matched the spec more closely.

2. I gave the assistant the `Planning Loop` spec again, plus a direct request to verify state flow for the walkthrough query from `planning.md`. It produced a state-checking script and suggested validating that the exact dict stored in `session["selected_item"]` was passed into `suggest_outfit()`, and that `session["outfit_suggestion"]` was passed unchanged into `create_fit_card()`. I kept the verification idea but simplified the script to fit the local environment, then used the result to confirm that the agent was not hardcoding intermediate values or re-prompting the user between steps.

The overall rule I followed was simple: use AI to review or stress-test the spec and implementation, but keep the final control flow, parser behavior, and error messages aligned with the written requirements and the test results.

## Data Sources

- `data/listings.json`: mock secondhand inventory.
- `data/wardrobe_schema.json`: wardrobe schema, example wardrobe, and empty wardrobe template.

Load them through `utils/data_loader.py`:

```python
from utils.data_loader import load_listings, get_example_wardrobe

listings = load_listings()
wardrobe = get_example_wardrobe()
```
