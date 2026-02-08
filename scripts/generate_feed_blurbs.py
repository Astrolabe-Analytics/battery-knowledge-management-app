"""
Generate tweet-style feed blurbs for papers with AI summaries.
Max 280 characters, punchy science journalism style.
"""
import json
import os
from pathlib import Path
from anthropic import Anthropic

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"

def generate_blurb(ai_summary: str, title: str) -> str:
    """Generate a 280-char feed blurb from AI summary using Claude API."""

    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    prompt = f"""Convert this research paper summary into a punchy, tweet-style blurb (max 280 characters).

Paper title: {title}

Full summary:
{ai_summary}

Requirements:
- Exactly 1-2 sentences, maximum 280 characters
- Lead with the key finding or result, not the method
- Informative but punchy, like a science journalist
- Use specific numbers/metrics when available
- No hashtags, no emojis

Example style: "Hybrid physics-informed neural net predicts battery discharge across 5 load levels with <3% EOD error — and a GP layer forecasts fleet-wide degradation without per-battery calibration."

Generate the blurb:"""

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}]
    )

    blurb = message.content[0].text.strip()

    # Ensure it's under 280 chars
    if len(blurb) > 280:
        blurb = blurb[:277] + "..."

    return blurb

def main():
    print("Generating feed blurbs for papers with AI summaries")
    print("=" * 70)

    # Load metadata
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Find papers with AI summaries but no feed blurb
    papers_to_process = [
        (fn, meta) for fn, meta in metadata.items()
        if meta.get('ai_summary') and not meta.get('feed_blurb')
    ]

    print(f"\nFound {len(papers_to_process)} papers needing feed blurbs\n")

    if not papers_to_process:
        print("All papers already have feed blurbs!")
        return

    generated_count = 0

    for filename, paper in papers_to_process:
        title = paper.get('title', 'Unknown')[:60]
        ai_summary = paper['ai_summary']

        print(f"\n{filename}")
        print(f"Title: {title}...")
        print(f"Summary length: {len(ai_summary)} chars")

        try:
            blurb = generate_blurb(ai_summary, paper.get('title', ''))
            paper['feed_blurb'] = blurb
            generated_count += 1

            print(f"Blurb ({len(blurb)} chars): {blurb}")
            print("SUCCESS")

        except Exception as e:
            print(f"ERROR: {e}")
            continue

    # Save
    if generated_count > 0:
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"\n{'=' * 70}")
        print(f"Generated {generated_count} feed blurbs")
        print("Saved to metadata.json")
    else:
        print("\nNo blurbs were generated")

if __name__ == "__main__":
    main()
