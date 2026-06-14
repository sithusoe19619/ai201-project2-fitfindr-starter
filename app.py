"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the three output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import html
import re

import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


APP_CSS = """
.gradio-container {
    max-width: 1120px !important;
}

.app-header {
    border-bottom: 1px solid #dfe3e8;
    margin-bottom: 18px;
    padding-bottom: 14px;
}

.app-header h1 {
    color: #20242a;
    font-size: 1.8rem;
    margin: 0 0 4px;
}

.app-header p {
    color: #616871;
    margin: 0;
}

.search-band {
    background: #f6f7f8;
    border: 1px solid #e1e4e8;
    border-radius: 8px;
    padding: 16px;
}

.results-shell {
    border: 1px solid #d9dde3;
    border-radius: 8px;
    overflow: hidden;
    background: #fff;
    color: #22272d;
}

.results-grid {
    display: grid;
    grid-template-columns: minmax(280px, 0.9fr) minmax(360px, 1.4fr);
}

.result-section {
    padding: 22px 24px;
}

.listing-section {
    border-right: 1px solid #e2e5e9;
}

.section-label {
    color: #69717a;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0;
    margin-bottom: 8px;
    text-transform: uppercase;
}

.listing-title {
    font-size: 1.3rem;
    line-height: 1.3;
    margin: 0 0 10px;
}

.listing-price {
    color: #176b52;
    font-size: 1.15rem;
    font-weight: 700;
}

.listing-source {
    color: #68717b;
    font-size: 0.9rem;
}

.meta-grid {
    display: grid;
    gap: 7px 14px;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    margin: 18px 0;
}

.meta-item {
    min-width: 0;
}

.meta-label {
    color: #7b838d;
    display: block;
    font-size: 0.73rem;
    margin-bottom: 1px;
}

.meta-value {
    color: #30353b;
    font-size: 0.9rem;
    overflow-wrap: anywhere;
}

.listing-description {
    border-top: 1px solid #eceef1;
    color: #555d66;
    font-size: 0.9rem;
    line-height: 1.55;
    margin: 0;
    padding-top: 14px;
}

.looks {
    display: grid;
    gap: 12px;
}

.look {
    background: #f7f8f9;
    border-left: 3px solid #4b7f6b;
    border-radius: 0 6px 6px 0;
    padding: 12px 14px;
}

.look:nth-child(2) {
    border-left-color: #b66a3c;
}

.look-title {
    font-size: 0.95rem;
    font-weight: 700;
    margin-bottom: 4px;
}

.look-copy {
    color: #505861;
    font-size: 0.9rem;
    line-height: 1.5;
}

.fit-card-section {
    background: #202a27;
    color: #f7faf8 !important;
    padding: 18px 24px 20px;
}

.fit-card-section .section-label {
    color: #b9c9c2 !important;
}

.fit-card-copy {
    color: #f7faf8 !important;
    font-size: 1rem;
    line-height: 1.6;
    margin: 0;
}

.fit-card-section p,
.fit-card-section span,
.fit-card-section div {
    color: inherit !important;
}

.empty-results,
.error-results {
    border: 1px solid #d9dde3;
    border-radius: 8px;
    padding: 28px;
    text-align: center;
}

.empty-results {
    color: #68717b;
}

.error-results {
    background: #fff8f4;
    border-color: #e5c4b2;
    color: #7a3f26;
}

@media (max-width: 760px) {
    .results-grid {
        grid-template-columns: 1fr;
    }

    .listing-section {
        border-bottom: 1px solid #e2e5e9;
        border-right: 0;
    }

    .meta-grid {
        grid-template-columns: 1fr;
    }
}
"""

EMPTY_RESULTS_HTML = """
<div class="empty-results">
    Search for a secondhand piece to see a listing, outfit ideas, and fit card.
</div>
"""


def _format_outfit_looks(outfit: str) -> str:
    """Convert the LLM's short Markdown look list into structured HTML."""
    clean = outfit.strip()
    matches = list(
        re.finditer(
            r"\*\*(Look\s+\d+\s*[—-]\s*[^*]+)\*\*\s*[-–—]?\s*",
            clean,
            flags=re.IGNORECASE,
        )
    )

    looks = []
    if matches:
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(clean)
            title = html.escape(match.group(1).strip())
            copy = clean[start:end].strip().lstrip("-").strip()
            looks.append((title, html.escape(copy)))
    else:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", clean) if part.strip()]
        for index, paragraph in enumerate(paragraphs[:2], start=1):
            looks.append((f"Look {index}", html.escape(paragraph.replace("**", ""))))

    return "".join(
        f'<div class="look"><div class="look-title">{title}</div>'
        f'<div class="look-copy">{copy}</div></div>'
        for title, copy in looks
    )


def _render_results(
    listing_text: str,
    outfit_text: str,
    fit_card_text: str,
) -> str:
    """Compose the three handler outputs into one organized results surface."""
    if not outfit_text and not fit_card_text:
        return f'<div class="error-results">{html.escape(listing_text)}</div>'

    item_lines = listing_text.splitlines()
    item = {
        "title": item_lines[0].removeprefix("## ").strip(),
        "summary": item_lines[2].replace("**", "").strip(),
        "size": "",
        "brand": "",
        "colors": "",
        "style": "",
        "description": item_lines[-1].strip(),
    }
    for line in item_lines:
        if line.startswith("- **Size:**"):
            item["size"] = line.split("**Size:**", 1)[1].strip()
        elif line.startswith("- **Brand:**"):
            item["brand"] = line.split("**Brand:**", 1)[1].strip()
        elif line.startswith("- **Colors:**"):
            item["colors"] = line.split("**Colors:**", 1)[1].strip()
        elif line.startswith("- **Style:**"):
            item["style"] = line.split("**Style:**", 1)[1].strip()

    summary_parts = item["summary"].split(" on ", 1)
    price = summary_parts[0]
    source = summary_parts[1] if len(summary_parts) > 1 else ""
    outfit = outfit_text.replace("## Outfit ideas", "", 1).strip()
    fit_card = fit_card_text.replace("## Your fit card", "", 1).strip().lstrip("> ").strip()

    return f"""
<div class="results-shell">
    <div class="results-grid">
        <section class="result-section listing-section">
            <div class="section-label">Top listing</div>
            <h2 class="listing-title">{html.escape(item["title"])}</h2>
            <div>
                <span class="listing-price">{html.escape(price)}</span>
                <span class="listing-source"> on {html.escape(source)}</span>
            </div>
            <div class="meta-grid">
                <div class="meta-item">
                    <span class="meta-label">Size</span>
                    <span class="meta-value">{html.escape(item["size"])}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Brand</span>
                    <span class="meta-value">{html.escape(item["brand"])}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Colors</span>
                    <span class="meta-value">{html.escape(item["colors"])}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Style</span>
                    <span class="meta-value">{html.escape(item["style"])}</span>
                </div>
            </div>
            <p class="listing-description">{html.escape(item["description"])}</p>
        </section>
        <section class="result-section">
            <div class="section-label">Outfit ideas</div>
            <div class="looks">{_format_outfit_looks(outfit)}</div>
        </section>
    </div>
    <section class="fit-card-section">
        <div class="section-label">Your fit card</div>
        <p class="fit-card-copy">{html.escape(fit_card)}</p>
    </section>
</div>
"""


def render_query(user_query: str, wardrobe_choice: str) -> str:
    """Run the existing handler and render its three outputs as one layout."""
    return _render_results(*handle_query(user_query, wardrobe_choice))


# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Args:
        user_query:     The text the user typed into the search box.
        wardrobe_choice: Either "Example wardrobe" or "Empty wardrobe (new user)".

    Returns:
        A tuple of three strings:
            (listing_text, outfit_suggestion, fit_card)
        Each string maps to one of the three output panels in the UI.

    TODO:
        1. Guard against an empty query (return early with an error message).
        2. Select the wardrobe based on wardrobe_choice.
        3. Call run_agent() with the query and selected wardrobe.
        4. If session["error"] is set, return the error in the first panel
           and empty strings for the other two.
        5. Otherwise, format session["selected_item"] into a readable listing_text
           string and return it along with session["outfit_suggestion"] and
           session["fit_card"].
    """
    if not user_query or not user_query.strip():
        return "Please enter what you're looking for.", "", ""

    if wardrobe_choice == "Example wardrobe":
        wardrobe = get_example_wardrobe()
    else:
        wardrobe = get_empty_wardrobe()

    session = run_agent(user_query.strip(), wardrobe)
    if session["error"]:
        return session["error"], "", ""

    item = session["selected_item"]
    brand = item.get("brand") or "Unbranded"
    listing_text = (
        f"## {item['title']}\n\n"
        f"**${item['price']:.2f}** on **{item['platform'].title()}**"
        f" · {item['condition'].title()} condition\n\n"
        f"- **Size:** {item['size']}\n"
        f"- **Brand:** {brand}\n"
        f"- **Colors:** {', '.join(item.get('colors') or [])}\n"
        f"- **Style:** {', '.join(item.get('style_tags') or [])}\n\n"
        f"{item['description']}"
    )

    outfit_text = f"## Outfit ideas\n\n{session['outfit_suggestion']}"
    fit_card_text = f"## Your fit card\n\n> {session['fit_card']}"

    return listing_text, outfit_text, fit_card_text


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "platform sneakers size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]

def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.HTML(f"<style>{APP_CSS}</style>")
        gr.HTML(
            """
            <header class="app-header">
                <h1>FitFindr</h1>
                <p>Find secondhand pieces and build outfits from your wardrobe.</p>
            </header>
            """
        )

        with gr.Group(elem_classes=["search-band"]):
            with gr.Row():
                query_input = gr.Textbox(
                    label="What are you looking for?",
                    placeholder="e.g. vintage graphic tee under $30, size M",
                    lines=1,
                    scale=3,
                )
                wardrobe_choice = gr.Radio(
                    choices=["Example wardrobe", "Empty wardrobe (new user)"],
                    value="Example wardrobe",
                    label="Wardrobe",
                    scale=2,
                )

            submit_btn = gr.Button("Find it", variant="primary")

        results_output = gr.HTML(value=EMPTY_RESULTS_HTML, padding=False)

        gr.Examples(
            examples=[[q] for q in EXAMPLE_QUERIES],
            inputs=[query_input],
            label="Try these queries",
        )

        submit_btn.click(
            fn=render_query,
            inputs=[query_input, wardrobe_choice],
            outputs=results_output,
        )
        query_input.submit(
            fn=render_query,
            inputs=[query_input, wardrobe_choice],
            outputs=results_output,
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
