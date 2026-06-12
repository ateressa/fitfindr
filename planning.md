# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock secondhand listings dataset for items that match a user's query. It filters by description keywords, optional size, and optional maximum price, then returns the best matches ranked by relevance.

**Input parameters:**
- `description` (str): Keywords or phrases describing the item the user wants, such as "vintage graphic tee" or "black combat boots".
- `size` (str | None): Optional size filter to narrow results, such as "M", "W30 L30", or "US 7".
- `max_price` (float | None): Optional maximum price ceiling. Only listings at or below this price should be returned.

**What it returns:**
A list of listing dictionaries sorted by best match first. Each dictionary represents one listing from `data/listings.json` and contains `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

**What happens if it fails or returns nothing:**
If no listings match the filters or the keyword score is zero for every candidate, return an empty list. The agent should stop early, set a helpful error message, and not call the outfit or fit-card tools.

---

### Tool 2: suggest_outfit

**What it does:**
Generates outfit advice for a thrifted item using the user's wardrobe. If the wardrobe has items, it suggests specific combinations using named wardrobe pieces; if the wardrobe is empty, it gives general styling guidance for the new item instead.

**Input parameters:**
- `new_item` (dict): A single listing dictionary from `search_listings`, including the item's title, description, category, style tags, size, price, colors, brand, and platform.
- `wardrobe` (dict): A wardrobe dictionary in the schema from `data/wardrobe_schema.json`. It should contain an `items` key whose value is a list of wardrobe item dictionaries with fields like `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`.

**What it returns:**
A non-empty string containing 1–2 outfit suggestions or styling tips. When the wardrobe has items, the string should mention specific wardrobe pieces by name and explain how to combine them with the new item. When the wardrobe is empty, the string should still be useful and describe what items, silhouettes, colors, or vibe would pair well.

**What happens if it fails or returns nothing:**
If the wardrobe has no items, do not fail. Instead, return general styling advice for the new item so the agent can continue. If the LLM call fails or returns an unusable response, the agent should stop early with a helpful error message rather than passing empty outfit text into the fit-card step.

---

### Tool 3: create_fit_card

**What it does:**
Turns the outfit suggestion and thrifted item into a short social-media-style caption. The caption should sound like a real OOTD post, mention the item name, price, and platform once each, and reflect the outfit vibe in casual language.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit`, describing how the new item should be styled.
- `new_item` (dict): The selected listing dictionary for the thrifted item, used to pull the item name, price, and platform into the caption.

**What it returns:**
A 2–4 sentence caption string suitable for Instagram or TikTok. It should feel natural and specific, not like a product description, and it should vary based on the item and outfit so different inputs produce different captions.

**What happens if it fails or returns nothing:**
If `outfit` is empty or only whitespace, return a descriptive error message string instead of calling the LLM. If the caption generation fails for any other reason, the agent should treat it as a tool failure and stop with a helpful error message.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
The planning loop is a straight-through pipeline with one early-exit branch:

1. Create a fresh session dict with `_new_session(query, wardrobe)`.
2. Parse the raw query into `session["parsed"]` with `description`, `size`, and `max_price`.
     - If the query includes a size phrase such as `size M` or `size 8`, extract that value into `session["parsed"]["size"]`.
     - If the query includes a price phrase such as `under $30`, extract `30.0` into `session["parsed"]["max_price"]`.
     - Remove size and price phrases from the description so `session["parsed"]["description"]` contains only the search keywords.
3. Call `search_listings()` with the parsed values.
4. Store the returned list in `session["search_results"]`.
     - If the list is empty, set `session["error"]` to a helpful message like `No listings matched your request. Try loosening the size, price, or description filters.` and return the session immediately.
     - Do not call `suggest_outfit()` or `create_fit_card()` after an empty search result.
5. If results are not empty, set `session["selected_item"] = session["search_results"][0]` so the top-ranked listing becomes the item passed to the next tools.
6. Call `suggest_outfit(session["selected_item"], wardrobe)` and store the returned string in `session["outfit_suggestion"]`.
     - If the returned string is empty or only whitespace, set `session["error"]` to a helpful outfit-generation error and return early.
7. Call `create_fit_card(session["outfit_suggestion"], session["selected_item"])` and store the result in `session["fit_card"]`.
8. Return the completed session.

The loop is done when either:
- the search step fails and the agent returns early with an error, or
- all three tools finish successfully and the session contains a selected listing, an outfit suggestion, and a fit card.

---

## State Management

**How does information from one tool get passed to the next?**
The agent passes data through a single session dictionary that is created once at the start of `run_agent()` and updated after each step. The session acts as the shared state container for the whole interaction.

The session tracks these fields:

- `query`: the original user message, kept for reference
- `parsed`: a dictionary with the extracted `description`, `size`, and `max_price`
- `search_results`: the full list returned by `search_listings()`
- `selected_item`: the first result from `search_results`, used as the item for styling and caption generation
- `wardrobe`: the wardrobe dict passed into the agent
- `outfit_suggestion`: the string returned by `suggest_outfit()`
- `fit_card`: the string returned by `create_fit_card()`
- `error`: `None` on success, or a helpful message if the run stops early

Each tool writes its output back into the session before the next step runs. `search_listings()` writes into `search_results`; the planning loop copies `search_results[0]` into `selected_item`; `suggest_outfit()` consumes `selected_item` and `wardrobe` and writes `outfit_suggestion`; `create_fit_card()` consumes `outfit_suggestion` and `selected_item` and writes `fit_card`. If any step fails, the agent sets `error` and returns the session immediately instead of continuing with incomplete state.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Set `session["error"]` to: `"Sorry, I couldn't find any listings matching {description} {size_if_provided} under ${max_price}. Try a different description, skip the size filter, or increase your budget."` Then return immediately without calling `suggest_outfit` or `create_fit_card`. |
| suggest_outfit | Wardrobe is empty | Do not fail. Return general styling advice such as: `"Since this is your first thrifted find, I'd suggest pairing it with basic neutral bottoms like jeans or simple trousers, and sneakers or boots for a grounded look. You could layer a simple jacket over it for structure."` Then continue to `create_fit_card`. |
| create_fit_card | Outfit input is empty or only whitespace | Return an error string: `"Could not generate a caption because the outfit description was incomplete. This is a system error."` The planning loop should store this in `session["error"]` and return the session without attempting the caption. |

---

## Architecture

```text
User query
     │
     ▼
Planning Loop -------------------------------------------------------------┐
     │                                                                     │
     │ create session: query, parsed, search_results, selected_item,       │
     │ wardrobe, outfit_suggestion, fit_card, error                        │
     ▼                                                                     │
Session State                                                              │
     │                                                                     │
     ├─► parse query → session["parsed"] = {description, size, max_price}  │
     │                                                                     │
     ├─► search_listings(description, size, max_price)                     │
     │       │                                                             │
     │       ├──► results = []                                             │
     │       │       └──► [ERROR] session["error"] = "No listings..."      │
     │       │                   return session                            │
     │       │                                                             │
     │       └──► results = [item, ...]                                    │
     │               ▼                                                     │
     │          session["search_results"] = results                        │
     │          session["selected_item"] = results[0]                      │
     │                                                                     │
     ├─► suggest_outfit(selected_item, wardrobe)                           │
     │       │                                                             │
     │       ├──► outfit = "" or whitespace                                │
     │       │       └──► [ERROR] session["error"] = "Outfit generation..."│
     │       │                   return session                            │
     │       │                                                             │
     │       └──► outfit = "..."                                           │
     │               ▼                                                     │
     │          session["outfit_suggestion"] = outfit                      │
     │                                                                     │
     └─► create_fit_card(outfit_suggestion, selected_item)                 │
               │                                                           │
               └──► session["fit_card"] = "..."                            │
                         ▼                                                 │
                    Return session                                         │
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

I’ll use Claude for the three tool functions in `tools.py` because each one has a narrow contract that can be implemented and checked independently.

For `search_listings()`, I’ll give Claude the Tool 1 section from `planning.md` plus the data shape from `utils/data_loader.py` and `data/listings.json`. I expect it to produce code that loads the listings once, filters by `description`, optional `size`, and optional `max_price`, scores matches by keyword overlap, removes zero-score items, and returns the sorted list. Before using it, I’ll verify that the code handles all three input parameters and returns an empty list when nothing matches.

For `suggest_outfit()`, I’ll give Claude the Tool 2 section from `planning.md`, the wardrobe schema from `data/wardrobe_schema.json`, and the architecture diagram so it understands how the item moves through the session. I expect it to produce code that branches on an empty wardrobe, builds a prompt with either general styling guidance or named wardrobe pieces, and calls the Groq client through the shared helper. Before using it, I’ll check that it uses `new_item` and `wardrobe` correctly, returns a non-empty string, and does not fail when `wardrobe["items"]` is empty.

For `create_fit_card()`, I’ll give Claude the Tool 3 section from `planning.md` and the Architecture diagram so it knows the caption step comes after outfit generation. I expect it to produce code that rejects empty outfit text, constructs a prompt using the item name, price, platform, and outfit, and returns a short caption string. Before using it, I’ll verify that it guards against blank input and includes the required item details in the prompt.

**Milestone 4 — Planning loop and state management:**

I’ll use Copilot for `agent.py` because the planning loop is mostly orchestration and state passing, which benefits from working directly against the existing file structure. I’ll give it the Planning Loop section, the State Management section, the Error Handling table, and the Architecture diagram from `planning.md`, plus the current `agent.py` skeleton. I expect it to produce a `run_agent()` implementation that parses the query, calls the tools in order, stores results in the session dict, returns early on empty search results, and stops if outfit generation fails. Before trusting the code, I’ll verify that each branch matches the written plan, that `selected_item`, `outfit_suggestion`, and `fit_card` are stored in the session at the right time, and that the early-return path sets `session["error"]`.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1 — Parse the query:**

The planning loop extracts the description, size, and price from the user's input:
- `description`: "vintage graphic tee"
- `size`: None (user didn't specify)
- `max_price`: 30.0

`session["parsed"] = {"description": "vintage graphic tee", "size": None, "max_price": 30.0}`

**Step 2 — Search for listings:**

Call `search_listings("vintage graphic tee", size=None, max_price=30.0)`.

The function loads the 40 mock listings, filters by price (≤$30), scores each by keyword overlap with "vintage" and "graphic tee", removes zero-score items, and returns the sorted list. This returns 3 matches, with the top result being: `lst_006 — Graphic Tee — 2003 Tour Bootleg Style, $24, good condition, Depop`.

`session["search_results"]` stores the full list. `session["selected_item"] = session["search_results"][0]`.

**Step 3 — Get outfit suggestion:**

Call `suggest_outfit(new_item=lst_006, wardrobe=example_wardrobe)`.

The function sees the wardrobe has items ("Baggy straight-leg jeans", "Chunky white sneakers", "Black cropped zip hoodie", etc.). It builds a prompt asking the LLM to suggest outfit combinations using the new band tee and named wardrobe pieces. The LLM returns:

`"Pair this faded band tee with your baggy straight-leg jeans and chunky white sneakers — perfect 90s energy. Layer your black cropped zip hoodie over it if you want more edge, or keep it minimal with just the tee tucked slightly in front."`

`session["outfit_suggestion"]` stores this string.

**Step 4 — Generate fit card:**

Call `create_fit_card(outfit=session["outfit_suggestion"], new_item=lst_006)`.

The function builds a prompt with the outfit description and item details (name, price, platform). The LLM returns:

`"thrifted this faded band tee off depop for $24 and the fit is immaculate. paired it with my baggy jeans and chunky white sneakers for full 90s nostalgia 🖤"`

`session["fit_card"]` stores this string.

**Final output to user:**

The Gradio app displays:
- **Top listing found:** "Graphic Tee — 2003 Tour Bootleg Style. $24. Good condition. Black. Depop." [full listing text]
- **Outfit idea:** "Pair this faded band tee with your baggy straight-leg jeans and chunky white sneakers — perfect 90s energy. Layer your black cropped zip hoodie over it if you want more edge, or keep it minimal with just the tee tucked slightly in front."
- **Your fit card:** "thrifted this faded band tee off depop for $24 and the fit is immaculate. paired it with my baggy jeans and chunky white sneakers for full 90s nostalgia 🖤"
