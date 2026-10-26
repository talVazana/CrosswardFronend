import argparse
import json
import os
import re
import sys

from PIL import Image
from google import genai
from google.genai import types

DEFAULT_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-3.5-flash"

PROMPT = """
Read the crossword puzzle image. Extract ONLY the clue list (the numbered clues,
not the grid). The clues are in Hebrew and are split into two groups: across (מאוזן/אופק)
and down (מאונך/אנכי).

Return a single JSON array. Each item must look exactly like:
{ "number": 1, "direction": "across", "text": "..." }

Rules:
- "number" is an integer (the clue number as printed).
- "direction" is "across" or "down" only.
- "text" is the full clue text exactly as printed, including any length hints in
  parentheses, for example "(5)", "(4,3)", and any markers like "(ש)" or "(מ)".
- Keep the Hebrew wording exactly as it appears. Do not translate and do not reorder.
- Output ONLY the JSON array. No markdown fences, no extra text.
"""


def get_api_key():
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _parse_json(text):
    if not text:
        raise ValueError("Empty response from the model")
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def _normalize(data):
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of clues")
    clues = []
    for item in data:
        if not isinstance(item, dict):
            continue
        number = item.get("number")
        direction = str(item.get("direction", "")).strip().lower()
        text = str(item.get("text", "")).strip()
        if direction in ("across", "horizontal", "מאוזן", "מאוזק", "אופק"):
            direction = "across"
        elif direction in ("down", "vertical", "מאונך", "אנכי"):
            direction = "down"
        else:
            raise ValueError(f"Unknown direction: {direction!r}")
        if number is None or not text:
            raise ValueError(f"Missing number or text in: {item!r}")
        clues.append({"number": int(number), "direction": direction, "text": text})
    order = {"across": 0, "down": 1}
    clues.sort(key=lambda c: (order.get(c["direction"], 2), c["number"]))
    return clues


def _generate(client, image, prompt, model):
    return client.models.generate_content(
        model=model,
        contents=[image, prompt],
        config=types.GenerateContentConfig(temperature=0.0),
    )


def extract_clues(image_path, model=None):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Cannot load image: {image_path}")
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY / GOOGLE_API_KEY environment variable")

    image = Image.open(image_path)
    client = genai.Client(api_key=api_key)
    primary = model or DEFAULT_MODEL

    try:
        response = _generate(client, image, PROMPT, primary)
    except Exception as exc:
        print(f"Model {primary} failed ({exc}), falling back to {FALLBACK_MODEL}...")
        response = _generate(client, image, PROMPT, FALLBACK_MODEL)

    text = getattr(response, "text", None)
    if text is None:
        text = "\n".join(
            part.text
            for candidate in response.candidates
            for part in candidate.content.parts
            if getattr(part, "text", None)
        )
    return _normalize(_parse_json(text))


def main():
    ap = argparse.ArgumentParser(description="Extract crossword clues with Google Gemini.")
    ap.add_argument("image", nargs="?", default="a.jpg", help="input image (default: a.jpg)")
    ap.add_argument("-o", "--out", default=None, help="output json (default: <image>_clues.json)")
    ap.add_argument("--model", default=None, help=f"model (default: {DEFAULT_MODEL})")
    args = ap.parse_args()

    out_path = args.out or os.path.splitext(args.image)[0] + "_clues.json"
    clues = extract_clues(args.image, model=args.model)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(clues, fh, indent=2, ensure_ascii=False)
    print(f"Extracted {len(clues)} clues -> {out_path}")


if __name__ == "__main__":
    main()
