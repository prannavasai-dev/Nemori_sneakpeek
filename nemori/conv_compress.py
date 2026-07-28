"""
conv_compress.py — Item 11: Conversation Light-Touch Compression

Applied only to type=V (conversation) blocks. Never touches type=C blocks.
Replaces common role prefixes with short forms and collapses excessive
blank lines (lossy-but-acceptable whitespace only).

Decompressor reverses via @c section in the ctxpack.
"""

import re

PREFIX_MAP = {
    'Human:': 'H:',
    'Assistant:': 'A:',
    'User:': 'U:',
    'System:': 'S:',
}


def light_touch_compress(text: str) -> tuple[str, dict[str, str]]:
    """
    Apply lightweight compression to conversation text.

    1. Replace verbose role prefixes ('Human:' -> 'H:')
    2. Collapse 3+ consecutive blank lines to 2

    Returns:
        (compressed_text, applied_map)
        applied_map maps short_form -> original_form for @c section.
    """
    applied: dict[str, str] = {}
    for original, short in PREFIX_MAP.items():
        if original in text:
            text = text.replace(original, short)
            applied[short] = original

    # Collapse 3+ consecutive blank lines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text, applied
