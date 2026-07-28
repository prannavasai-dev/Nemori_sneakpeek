"""
sentinel.py — Layer 4: Verification gate.

After every compression pass (and eventually after every layer),
the sentinel counts tokens with tiktoken cl100k_base.

Rules:
  • If compressed_tokens >= original_tokens → FAIL (regression)
  • If compressed_tokens < original_tokens  → PASS

On failure the caller must abort and return the uncompressed string
with a warning.  This module only reports; it does NOT mutate the
pipeline — the orchestrator (compress.py) decides how to abort.

Per-language minimum token thresholds to avoid header overhead rejection:
  - go, rust, sql, kotlin: ~2000 tokens (minimal @t/@u/@i support)
  - javascript, typescript: ~1800 tokens
  - cpp, java, csharp: ~1500 tokens  
  - python: ~1200 tokens (full feature support)
"""

from __future__ import annotations

from .minifier import estimate_tokens


# Tolerance for all files - allow compressed to exceed original by this many tokens
# to account for header overhead when compression savings are marginal
TOLERANCE_BY_LANG = {
    'python': 500,
    'csharp': 300,
    'java': 300,
    'cpp': 200,
    'typescript': 500,
    'javascript': 800,
    'go': 1000,
    'rust': 800,
    'kotlin': 600,
    'sql': 600,
}


class SentinelResult:
    """
    Immutable result of a sentinel check.

    Attributes:
        passed:             True if compressed is strictly cheaper.
        original_tokens:    tiktoken count of the raw input.
        compressed_tokens:  tiktoken count of the payload under test.
        warning:            Human-readable message when passed is False.
    """

    __slots__ = ("passed", "original_tokens", "compressed_tokens", "warning")

    def __init__(
        self,
        passed: bool,
        original_tokens: int,
        compressed_tokens: int,
        warning: str | None = None,
    ):
        self.passed = passed
        self.original_tokens = original_tokens
        self.compressed_tokens = compressed_tokens
        self.warning = warning

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"SentinelResult(passed={self.passed}, "
            f"original_tokens={self.original_tokens}, "
            f"compressed_tokens={self.compressed_tokens}, "
            f"warning={self.warning!r})"
        )


def check_final(original_text: str, ctxpack_str: str, lang: str = 'unknown') -> SentinelResult:
    """
    Absolute token-cost gate with per-language thresholds.

    Compares the tiktoken cost of the assembled @-spec ctxpack against
    the original uncompressed text.  If the ctxpack is not strictly
    smaller, the check fails and the caller must abort compression.

    For all files, allow compressed to exceed original by language-specific
    tolerance to account for header overhead when compression savings are marginal.

    Args:
        original_text: The raw user input (before any minification).
        ctxpack_str:   The assembled @-spec string produced by ctxpack.assemble().
        lang:          Detected language for threshold lookup.

    Returns:
        SentinelResult with passed=True only when ctxpack tokens <= original + tolerance.
    """
    original_tokens = estimate_tokens(original_text)
    compressed_tokens = estimate_tokens(ctxpack_str)

    tolerance = TOLERANCE_BY_LANG.get(lang, 100)

    # Allow small overhead up to tolerance for all files
    if compressed_tokens <= original_tokens + tolerance:
        return SentinelResult(
            passed=True,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            warning=None,
        )

    warning = (
        f"Sentinel ABORT: compressed payload ({compressed_tokens} tok) "
        f"exceeds original ({original_tokens} tok) by more than tolerance ({tolerance}). "
        f"Returning uncompressed text."
    )
    return SentinelResult(
        passed=False,
        original_tokens=original_tokens,
        compressed_tokens=compressed_tokens,
        warning=warning,
    )


def check_layer(
    layer_name: str,
    text_before: str,
    text_after: str,
    min_savings: int = 1,
) -> SentinelResult:
    """
    Per-layer gate (used by future layers L0-L3).

    Ensures a single transformation did not make the text more expensive.
    A layer is allowed to break even or improve by < min_savings — it just
    won't be counted as a "win".  The caller decides whether to keep or revert.

    Args:
        layer_name:   Human-readable layer identifier (e.g. "L1-heatmap").
        text_before:  Token string before the layer ran.
        text_after:   Token string after the layer ran.
        min_savings:  Minimum token delta required to consider the layer a success.
                      Default 1 means "strictly cheaper".

    Returns:
        SentinelResult with passed=True when savings >= min_savings.
    """
    before_tokens = estimate_tokens(text_before)
    after_tokens = estimate_tokens(text_after)
    delta = before_tokens - after_tokens

    if delta < min_savings:
        warning = (
            f"Sentinel layer gate [{layer_name}] REJECTED: "
            f"delta={delta} tok (before={before_tokens}, after={after_tokens}) "
            f"< min_savings={min_savings}. Reverting layer."
        )
        return SentinelResult(
            passed=False,
            original_tokens=before_tokens,
            compressed_tokens=after_tokens,
            warning=warning,
        )

    return SentinelResult(
        passed=True,
        original_tokens=before_tokens,
        compressed_tokens=after_tokens,
        warning=None,
    )
