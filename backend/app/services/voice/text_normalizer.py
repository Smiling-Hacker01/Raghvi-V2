"""Conversational text normalizer for high-fidelity, consistent TTS synthesis."""

import re

# Comprehensive emoji regex covering standard Unicode emojis and pictographs
_EMOJI_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff]|[\u200d\u200c\u200b]"
    r"|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50\u2b55]"
    r"|[\ufe00-\ufe0f]|[\u203c-\u2049]|[\u25aa-\u25fe]",
    flags=re.UNICODE,
)


def clean_text_for_speech(text: str, is_hindi: bool = False) -> str:
    """
    Clean and normalize raw LLM text into smooth, human-conversational prose for TTS.

    Transformations:
    - Strips code fences and inline backticks
    - Strips markdown headers, bold, italics, strikethrough, blockquotes
    - Normalizes markdown links to their anchor text and removes raw URLs
    - Normalizes bullet points and numbered lists into naturally paused sentences
    - Strips emojis and stray symbols that cause neural vocoder stumbling
    - Normalizes common abbreviations ('AI' -> 'A.I.', 'e.g.' -> 'for example')
    - Applies authentic pronunciation phonetic anchors for 'Raghvi'
    - Collapses irregular whitespace into clean sentence punctuation
    """
    if not text:
        return ""

    cleaned = text

    # 1. Remove XML/HTML residue tags (e.g., <thought>, <chat_text>, <emotion>, <voice_text>)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)

    # 2. Handle code blocks: replace multi-line code fences with a brief conversational phrase
    cleaned = re.sub(
        r"```[a-zA-Z0-9_\-\+]*\n.*?\n```",
        " Here is the code. ",
        cleaned,
        flags=re.DOTALL,
    )
    cleaned = re.sub(r"```.*?```", " ", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)

    # 3. Clean markdown links: [text](http://...) -> text
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)

    # 4. Remove standalone URLs (http:// or https://)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)

    # 5. Clean markdown headers (# Header -> Header.)
    cleaned = re.sub(r"^\s*#{1,6}\s+(.+)$", r"\1.", cleaned, flags=re.MULTILINE)

    # 6. Normalize list items to ensure they end with a period for natural breathing pauses
    def _normalize_list_item(match: re.Match) -> str:
        item_text = match.group(1).strip()
        if not item_text:
            return ""
        if not item_text.endswith((".", "!", "?", "।", ":")):
            item_text += "."
        return " " + item_text + " "

    # Bullet lists (- Item, * Item, • Item)
    cleaned = re.sub(r"^\s*[-*•]\s+(.+)$", _normalize_list_item, cleaned, flags=re.MULTILINE)
    # Numbered lists (1. Item, 2. Item)
    cleaned = re.sub(r"^\s*\d+\.\s+(.+)$", _normalize_list_item, cleaned, flags=re.MULTILINE)

    # 7. Strip blockquote indicators (> Quote)
    cleaned = re.sub(r"^\s*>\s*", "", cleaned, flags=re.MULTILINE)

    # 8. Strip markdown emphasis (*bold*, **bold**, _italic_, __italic__, ~~strike~~)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"_([^_]+)_", r"\1", cleaned)
    cleaned = re.sub(r"~~([^~]+)~~", r"\1", cleaned)

    # 9. Strip emojis and pictographs
    cleaned = _EMOJI_PATTERN.sub(" ", cleaned)

    # 10. Expand common abbreviations for natural acoustic prosody
    abbreviations = [
        (r"\bAI\b", "A.I."),
        (r"\be\.g\.,?\b", "for example"),
        (r"\bi\.e\.,?\b", "that is"),
        (r"\betc\.\b", "etcetera"),
        (r"\bvs\.\b", "versus"),
        (r"\bAPI\b", "A.P.I."),
        (r"\bUI\b", "U.I."),
    ]
    for pattern, replacement in abbreviations:
        cleaned = re.sub(pattern, replacement, cleaned)

    # 11. Pronunciation Normalization for Raghvi's name
    if is_hindi:
        # In Hindi/Devanagari contexts, anchor directly to Devanagari script
        cleaned = re.sub(r"\b[Rr]a+gh+vi\b", "राघवी", cleaned)
    else:
        # In English/Hinglish contexts, anchor vowel length so it is never pronounced "Rag-vee"
        cleaned = re.sub(r"\b[Rr]aghvi\b", "Raaghvi", cleaned)

    # 12. Normalize whitespace, consecutive newlines, and punctuation spacing
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    # Convert consecutive newlines to full stop so paragraph breaks become natural pauses
    cleaned = re.sub(r"\n\s*\n+", ". ", cleaned)
    cleaned = re.sub(r"\n+", " ", cleaned)

    # Avoid duplicate punctuation like "..", ".,", etc.
    cleaned = re.sub(r"\.+", ".", cleaned)
    cleaned = re.sub(r"\.\s*,\s*", ", ", cleaned)
    cleaned = re.sub(r"\s+([.,!?:;।])", r"\1", cleaned)

    return cleaned.strip()
