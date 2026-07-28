"""
tokens.py — Shared token counting and net-gain calculation.

Every token-cost decision in the compression pipeline calls this module —
one tokenizer reference, no drift between features.
"""

try:
    import tiktoken as _tiktoken
    _ENC = _tiktoken.get_encoding('cl100k_base')
except Exception:
    _ENC = None


def count_tokens(text: str) -> int:
    """Exact token count via tiktoken cl100k_base, fallback to heuristic."""
    if _ENC is not None:
        return len(_ENC.encode(text))
    return max(1, len(text) // 4)


def net_gain(original: str, replacement: str, overhead: str = '') -> int:
    """
    Calculate net token gain of replacing `original` with `replacement`,
    accounting for any `overhead` cost (e.g. dictionary entry).

    Returns positive int when the replacement saves tokens.
    """
    return count_tokens(original) - count_tokens(replacement) - count_tokens(overhead)
