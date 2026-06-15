# FitFindr

FitFindr is a multi-tool AI agent that searches a mock secondhand marketplace,
suggests outfits using a user's wardrobe, and creates a short shareable fit
card. The agent uses a conditional planning loop, so it decides whether to
continue based on each tool's result instead of calling every tool
unconditionally.

## Setup

Install the dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root and add a Groq API key:

```text
GROQ_API_KEY=your_key_here
```

The `.env` file is ignored by Git and should never be committed.

Run the app:

```bash
python app.py
```

Open the local URL printed by Gradio. The port may not always be `7860`.

Run the tests:

```bash
python -m pytest tests/
```

The LLM-backed tests call the real Groq API, so they require the API key and an
internet connection.

## Tool Inventory

### `search_listings`

```python
search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]
```

- **Purpose:** Search the 40 mock secondhand listings and rank relevant matches.
- **Inputs:**
  - `description`: Item keywords such as `"vintage graphic tee"`.
  - `size`: Optional clothing or shoe size such as `"M"` or `"8"`.
  - `max_price`: Optional inclusive price ceiling.
- **Output:** Listing dictionaries sorted by relevance. Each dictionary includes
  `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`,
  `price`, `colors`, `brand`, and `platform`.
- **Failure result:** Returns `[]` when no listing satisfies the search.

### `suggest_outfit`

```python
suggest_outfit(new_item: dict, wardrobe: dict) -> str
```

- **Purpose:** Use Groq's `llama-3.3-70b-versatile` model to suggest one or two
  complete outfits containing the selected listing.
- **Inputs:**
  - `new_item`: The listing selected by the planning loop.
  - `wardrobe`: A dictionary with an `items` list containing the user's clothing.
- **Output:** A non-empty string with concise, labeled outfit ideas.
- **Failure fallback:** If the wardrobe is empty, it returns general styling
  advice instead of crashing.

### `create_fit_card`

```python
create_fit_card(outfit: str, new_item: dict) -> str
```

- **Purpose:** Turn the outfit suggestion into a short social-media-style caption.
- **Inputs:**
  - `outfit`: The exact suggestion returned by `suggest_outfit`.
  - `new_item`: The same selected listing used by `suggest_outfit`.
- **Output:** A casual 2-3 sentence caption mentioning the item, price, platform,
  and outfit vibe.
- **Failure result:** Returns
  `"Cannot create a fit card without an outfit suggestion."` when `outfit` is
  empty.

## Planning Loop

`run_agent()` creates a fresh session and parses the natural-language query into
`description`, `size`, and `max_price`.

1. It calls `search_listings()` and stores the returned list.
2. If the list is empty, it records an actionable error and returns immediately.
   It does not call the other tools without an item.
3. If results exist, it selects `results[0]` and stores it as `selected_item`.
4. It passes that exact dictionary and the current wardrobe to
   `suggest_outfit()`.
5. If the outfit is empty, it records an error and returns before caption
   generation.
6. It passes the stored outfit suggestion and the same selected item to
   `create_fit_card()`.
7. It returns the completed session containing the listing, outfit, and fit card.

This branching is what makes the workflow an agent loop rather than an
unconditional sequence of three function calls.

## State Management

One session dictionary is the source of truth for each interaction:

| Field | Meaning |
|---|---|
| `query` | Original natural-language request |
| `parsed` | Extracted description, size, and max price |
| `search_results` | Ranked listing dictionaries |
| `selected_item` | Top listing passed to both LLM tools |
| `wardrobe` | Example or empty wardrobe selected in the UI |
| `outfit_suggestion` | Result passed from `suggest_outfit` to `create_fit_card` |
| `fit_card` | Final shareable caption |
| `error` | Failure message when the workflow stops early |

The user does not need to re-enter information between steps. Each tool receives
its inputs from this shared session state.

## Error Handling

| Tool or stage | Triggered failure | Agent behavior |
|---|---|---|
| `search_listings` | `"designer ballgown"` in size `XXS` under `$5` returns `[]` | Reports which constraints had no exact match, suggests removing a filter or broadening the description, and skips both LLM tools. |
| `suggest_outfit` | The wardrobe contains no items | Calls Groq for general advice about compatible bottoms, shoes, layers, and accessories. |
| `create_fit_card` | The outfit string is empty | Returns a descriptive error string without making an LLM call or raising an exception. |
| Query handler | The user submits blank input | Displays `"Please enter what you're looking for."` and does not start the agent. |

A search regression test also verifies that shoe size `8` does not match waist
size `W28`. The search now requires both the requested item type and exact
numeric size to match, preventing a request for boots from returning jeans.

## Data

`data/listings.json` contains 40 mock listings across tops, bottoms, outerwear,
shoes, and accessories.

`data/wardrobe_schema.json` contains:

- The wardrobe item schema
- A 10-item example wardrobe
- An empty wardrobe for new-user testing

The project uses the helpers in `utils/data_loader.py` rather than reading these
files directly inside the agent tools.

## Spec Reflection

The final implementation follows the original specification: three tools have
defined interfaces, state flows through a single session, and the planning loop
returns early when a previous step has no useful output.

Testing changed some implementation details. The first search version used
substring size matching, so a request for shoe size `8` could incorrectly match
`W28` jeans. I replaced that with exact numeric size matching and added item-type
validation plus a regression test. I also made the no-results message identify
the failed description and filters so the response is more useful than a generic
error.

## AI Usage

I used ChatGPT/Codex in two specific parts of the project:

1. **Individual tools:** I provided the Tools and Error Handling sections from
   `planning.md`, plus the listing and wardrobe schemas. The AI produced initial
   implementations for the three functions in `tools.py`. Before using them, I
   checked each signature and failure path, then changed the search logic to
   prevent color-only and partial-size matches.
2. **Planning loop:** I provided the Planning Loop, State Management, and
   Architecture diagram from `planning.md`. The AI produced the initial
   `run_agent()` and `handle_query()` wiring. I reviewed the generated flow,
   verified that it returned early after an empty search, and added tests that
   proved the downstream tools were not called on that path.

I treated the AI output as a draft: I reviewed it against the written spec,
tested it with normal and failure inputs, and overrode behavior when the tests
showed a mismatch.

## Project Structure

```text
.
├── agent.py
├── app.py
├── tools.py
├── planning.md
├── requirements.txt
├── data/
│   ├── listings.json
│   └── wardrobe_schema.json
├── tests/
│   └── test_tools.py
└── utils/
    └── data_loader.py
```
