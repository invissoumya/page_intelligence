import os
import json
import argparse
import requests
from bs4 import BeautifulSoup

# This script reads a JSON of page sections (produced by extract_sections.py),
# summarizes each section and asks Claude to classify it into one of the
# following categories: hero, offer, testimonial, content, video, cta, faq.
# The results are written to an output JSON file.

CLAUDE_API_URL = "https://api.anthropic.com/v1/complete"  # or other Claude endpoint


def html_to_text(html: str) -> str:
    """Utility that strips HTML tags and returns plain text."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def classify_with_claude(text: str) -> dict:
    """Send a classification request to the Claude API.

    Expects CLAUDE_API_KEY (or ANTHROPIC_API_KEY) in the environment.
    Returns the parsed JSON response from the API.
    """
    api_key = os.environ.get("CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Environment variable CLAUDE_API_KEY not set")

    prompt = (
        "You are given a section of a webpage. Classify it into one of the "
        "following categories: hero, offer, testimonial, content, video, cta, faq. "
        "Return a JSON object with a single key \"category\" whose value is the "
        "chosen label.\n\n" + text
    )

    payload = {
        "model": "claude-v1.3",  # adjust as needed
        "prompt": prompt,
        "max_tokens": 60,
        "temperature": 0,
    }
    headers = {"x-api-key": api_key}

    resp = requests.post(CLAUDE_API_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Classify sections via Claude")
    parser.add_argument("input", help="Path to JSON file produced by extract_sections.py")
    parser.add_argument("-o", "--output", default="analysis/section_classification.json",
                        help="Output JSON file to write classifications")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        sections_data = json.load(f)

    classification_results = {}

    for url, sections in sections_data.items():
        classification_results[url] = {}
        for name, fragments in sections.items():
            text = " ".join(html_to_text(frag) for frag in fragments)
            if not text.strip():
                # no content to classify
                continue
            try:
                result = classify_with_claude(text)
            except Exception as e:
                result = {"error": str(e)}
            classification_results[url][name] = {
                "summary": text,
                "claude_response": result,
            }

    # ensure output directory exists
    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir)

    with open(args.output, "w", encoding="utf-8") as out_f:
        json.dump(classification_results, out_f, ensure_ascii=False, indent=2)

    print(f"Classification written to {args.output}")


if __name__ == "__main__":
    main()
