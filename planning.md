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
Searches the mock secondhand listings dataset for items that match the user's requested item description, optional size, and optional maximum price. It filters out listings that violate hard constraints, scores the remaining listings by keyword relevance, and returns the best matches first.

**Input parameters:**
- `description` (str): The item keywords extracted from the user query, such as `"vintage graphic tee"` or `"black combat boots"`.
- `size` (str | None): An optional size filter extracted from the user query, such as `"M"`, `"S/M"`, `"W30"`, or `"US 8"`. If `None`, the tool should not filter by size.
- `max_price` (float | None): An optional maximum price extracted from the user query, such as `30.0`. If `None`, the tool should not filter by price.

**What it returns:**
A list of listing dictionaries sorted by relevance, with the strongest match first. Each returned listing contains `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

**What happens if it fails or returns nothing:**
The tool returns an empty list instead of crashing. The agent should store the empty list in `session["search_results"]`, set `session["error"]` to a helpful message such as `"No listings found for that search. Try broader keywords, removing the size filter, or raising your max price."`, and return early without calling `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Suggests one or two complete outfit combinations that include the selected thrifted listing. When the user has wardrobe items, it should reference specific pieces from the wardrobe; when the wardrobe is empty, it should provide general styling advice that still helps the user understand how to wear the item.

**Input parameters:**
- `new_item` (dict): The selected listing dictionary from `search_listings`, containing fields such as `title`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.
- `wardrobe` (dict): A wardrobe dictionary with an `items` key. Each wardrobe item may include `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`.

**What it returns:**
A non-empty string containing practical outfit suggestions. The response should describe the full look, including the new item plus compatible bottoms, shoes, accessories, layers, or styling details. If possible, it should mention specific wardrobe item names.

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, the tool should still return a useful general styling suggestion rather than failing. If the tool cannot produce a usable suggestion for another reason, the agent should set `session["error"]` to `"I found a listing, but couldn't generate a styling suggestion for it. Try again with a more detailed wardrobe or a different item."` and return early before calling `create_fit_card`.

---

### Tool 3: create_fit_card

**What it does:**
Turns the outfit suggestion and selected listing into a short, shareable caption that sounds like a real social post. The caption should connect the thrifted item to the styling idea and mention the platform and price naturally.

**Input parameters:**
- `outfit` (str): The outfit suggestion returned by `suggest_outfit`.
- `new_item` (dict): The selected listing dictionary used in the outfit, including `title`, `price`, `platform`, `condition`, `colors`, and `style_tags`.

**What it returns:**
A 2-4 sentence string that can be used as an Instagram or TikTok outfit caption. It should mention the item name, price, and platform once, and should describe the outfit vibe in casual, specific language.

**What happens if it fails or returns nothing:**
If `outfit` is missing, empty, or whitespace-only, the tool should return a clear error string such as `"Cannot create a fit card without an outfit suggestion."` rather than raising an exception. The agent should store that message in `session["error"]` and return the session without presenting it as a finished caption.

---

### Additional Tools (if any)

No additional tools are planned for the required version. Stretch tools such as price comparison, style memory, trend awareness, or retry logic will be planned separately before implementation.

---

## Planning Loop

**How does your agent decide which tool to call next?**
The agent starts each interaction by creating a fresh session dictionary with the original query, wardrobe, empty parsed fields, empty results, and `error=None`. It parses the query into `description`, `size`, and `max_price`, stores those values in `session["parsed"]`, then calls `search_listings(description, size, max_price)`.

After `search_listings` runs, the agent stores the result list in `session["search_results"]`. If the list is empty, the agent sets `session["error"]` to a message explaining that no listings matched and suggesting broader keywords, fewer filters, or a higher budget, then returns the session immediately. If the list has results, the agent sets `session["selected_item"] = session["search_results"][0]` and continues.

Next, the agent calls `suggest_outfit(session["selected_item"], session["wardrobe"])`. If the returned suggestion is empty or unusable, the agent sets `session["error"]` to a styling failure message and returns early. Otherwise, it stores the string in `session["outfit_suggestion"]`.

Finally, the agent calls `create_fit_card(session["outfit_suggestion"], session["selected_item"])`. If the fit card is empty or reports that the outfit input was missing, the agent stores that issue in `session["error"]`. Otherwise, it stores the caption in `session["fit_card"]` and returns the completed session.

---

## State Management

**How does information from one tool get passed to the next?**
The session dictionary is the single source of truth for one user interaction. It tracks `query`, `parsed`, `search_results`, `selected_item`, `wardrobe`, `outfit_suggestion`, `fit_card`, and `error`.

The parsed query values are passed into `search_listings`. The first search result is saved as `selected_item` and passed into `suggest_outfit` with the current wardrobe. The outfit suggestion is saved as `outfit_suggestion` and passed into `create_fit_card` with the same selected item. Any tool failure is stored in `error`, which tells the app or CLI to show the error message instead of continuing the workflow.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Set `session["error"] = "No listings found for that search. Try broader keywords, removing the size filter, or raising your max price."` and return early without calling the other tools. |
| suggest_outfit | Wardrobe is empty | Continue without failing. Ask the LLM for general styling advice for the selected item and explain what kinds of bottoms, shoes, layers, or accessories would work. |
| create_fit_card | Outfit input is missing or incomplete | Return `"Cannot create a fit card without an outfit suggestion."`; the agent stores that in `session["error"]` and does not present a completed caption. |

---

## Architecture

```text
User query
    │
    ▼
Planning Loop ───────────────────────────────────────────┐
    │                                                    │
    ├─► search_listings(description, size, max_price)    │
    │       │ results=[]                                 │
    │       ├──► [ERROR] "No listings found..." → return │
    │       │                                            │
    │       │ results=[item, ...]                        │
    │       ▼                                            │
    │   Session: selected_item = results[0]              │
    │       │                                            │
    ├─► suggest_outfit(selected_item, wardrobe)          │
    │       │                                            │
    │   Session: outfit_suggestion = "..."               │
    │       │                                            │
    └─► create_fit_card(outfit_suggestion, selected_item)│
            │                                            │
        Session: fit_card = "..."                        │
            │                                            └─ error path returns here
            ▼
        Return session
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**
I will use ChatGPT/Codex to help implement the three required tools in `tools.py`. I will give it the **Tools** section, the **Error Handling** table, and the data schema details from the Milestone 1 exploration. I expect it to produce implementations for `search_listings`, `suggest_outfit`, and `create_fit_card` that match the documented function signatures, use `load_listings()` from `utils/data_loader.py`, and handle empty or invalid inputs without crashing.

Before trusting the generated code, I will inspect that `search_listings` filters by price and size, scores matches using listing fields, and returns an empty list for no matches. I will test the tools individually with at least three searches: a normal match like `"vintage graphic tee under $30"`, a size-specific match, and a no-results query like `"designer ballgown size XXS under $5"`. I will also test `suggest_outfit` with both the example wardrobe and the empty wardrobe.

**Milestone 4 — Planning loop and state management:**
I will use ChatGPT/Codex to help implement `run_agent` in `agent.py` and `handle_query` in `app.py`. I will give it the **Planning Loop**, **State Management**, **Error Handling**, **Architecture** diagram, and **A Complete Interaction** sections from this document. I expect it to produce a planning loop that creates a session, parses the user query, calls tools conditionally based on previous results, stores each tool result in session state, and returns early on errors.

Before using the implementation, I will verify that the agent does not call `suggest_outfit` when search returns no results, does not call `create_fit_card` when there is no outfit suggestion, and returns a session with either a final fit card or a clear error message. I will run `python agent.py` for the CLI demo and then run the Gradio app to confirm the UI shows the listing, outfit idea, and fit card in the correct panels.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

FitFindr takes a user's natural language request, extracts the item description plus optional filters like size and max price, then uses that information to search the mock secondhand listings. If a matching item is found, the selected listing is passed into the outfit suggestion tool along with the user's wardrobe, and that outfit is then passed into the fit card tool to create a short shareable caption. If search returns no results, the agent stops before calling the styling tools and tells the user how to adjust the request.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent parses the query into `description="vintage graphic tee"`, `size=None`, and `max_price=30.0`, then calls `search_listings("vintage graphic tee", size=None, max_price=30.0)`. The search tool checks listing titles, descriptions, categories, style tags, colors, sizes, prices, brands, and platforms, then returns matching listings sorted by relevance.

**Step 2:**
The agent stores the returned listings in `session["search_results"]`. A successful return value is a list like `[{"id": "lst_002", "title": "Y2K Baby Tee — Butterfly Print", "description": "...", "category": "tops", "style_tags": ["y2k", "vintage", "graphic tee", "cottagecore"], "size": "S/M", "condition": "excellent", "price": 18.0, "colors": ["white", "pink", "purple"], "brand": None, "platform": "depop"}, ...]`. The agent selects the first listing and stores it as `session["selected_item"]`.

**Step 3:**
The agent calls `suggest_outfit(session["selected_item"], session["wardrobe"])`. The outfit tool uses wardrobe item names, categories, colors, style tags, and notes to return a string such as `"Pair the butterfly baby tee with your baggy straight-leg jeans, chunky white sneakers, and black crossbody bag for a casual Y2K streetwear look. Add the vintage black denim jacket if you want more structure."` The agent stores this string in `session["outfit_suggestion"]`.

**Step 4:**
The agent calls `create_fit_card(session["outfit_suggestion"], session["selected_item"])`. The fit card tool returns a 2-4 sentence caption such as `"Found this Y2K butterfly baby tee on depop for $18 and it instantly gave the jeans-and-sneakers combo more personality. Styling it with baggy denim, chunky white sneakers, and a black crossbody for an easy early-2000s thrifted fit."` The agent stores the caption in `session["fit_card"]`.

**Error path:**
If `search_listings` returns `[]`, the agent sets `session["error"] = "No listings found for that search. Try broader keywords, removing the size filter, or raising your max price."` and returns immediately. The agent does not call `suggest_outfit` or `create_fit_card` because there is no selected item to style.

**Final output to user:**
The user sees three pieces of information: the top listing found with title, price, platform, condition, size, colors, and style tags; a practical outfit idea using their wardrobe when possible; and a short fit card caption. If search fails, the user sees the no-results error message and actionable suggestions instead of empty outfit or caption panels.
