"""
heatmap.py — Layer 1: Heat Map Scanner

Scans each chunk and scores it hot (compress) or cold (pass-through).
Also extracts relationship signals (imports, function calls) for
grid placement in Layer 5 — related blocks land adjacent on the
64x64 grid, making it a visual dependency map.

Hot score dimensions:
  1. Token frequency   — repeated tiktoken sequences
  2. Line similarity   — Levenshtein ratio between adjacent lines
  3. Shannon entropy   — low entropy per 10-line window = repetitive = hot
  4. Identifier length — avg identifier > 8 chars = compression candidate

Relationship signals (Graphify-inspired):
  - block_imports: names imported by this block
  - block_calls:   function names called by this block

Threshold: hot_score >= 0.5 → is_hot = True → goes to competition engine
           hot_score <  0.5 → is_hot = False → passes through untouched
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field

try:
    from .minifier import _enc
    def _tok_count(text: str) -> int:
        if _enc is not None:
            return len(_enc.encode(text))
        return max(1, len(text) // 4)
except Exception:
    def _tok_count(text: str) -> int:
        return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class HeatResult:
    """
    Result of scanning one block.

    Attributes:
        hot_score:        float 0.0–1.0. Higher = more compressible.
        is_hot:           True when hot_score >= HOT_THRESHOLD.
        entropy:          Shannon entropy of the block (lower = more repetitive).
        repetition_score: Fraction of tokens that are repeated (0–1).
        similarity_score: Average Levenshtein similarity between adjacent lines (0–1).
        id_length_score:  Score based on average identifier length (0–1).
        block_imports:    Names imported by this block (for grid adjacency).
        block_calls:      Function names called by this block (for grid adjacency).
    """
    hot_score:        float
    is_hot:           bool
    entropy:          float
    repetition_score: float
    similarity_score: float
    id_length_score:  float
    block_imports:    list[str] = field(default_factory=list)
    block_calls:      list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HOT_THRESHOLD = 0.3

# Dimension weights — must sum to 1.0
_W_REPETITION  = 0.35
_W_SIMILARITY  = 0.25
_W_ENTROPY     = 0.25
_W_ID_LENGTH   = 0.15

_ENTROPY_WINDOW = 10   # lines per Shannon entropy window
_MIN_ID_LENGTH  = 8    # identifiers longer than this score hot


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _levenshtein_ratio(a: str, b: str) -> float:
    """Normalised Levenshtein similarity in [0, 1]."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    la, lb = len(a), len(b)
    # Use DP with two rows to keep memory O(min(la,lb))
    if la < lb:
        a, b, la, lb = b, a, lb, la
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * lb
        for j, cb in enumerate(b, 1):
            curr[j] = min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + (0 if ca == cb else 1),
            )
        prev = curr
    dist = prev[lb]
    return 1.0 - dist / max(la, lb)


def _shannon_entropy(tokens: list[int]) -> float:
    """Shannon entropy of a token-id sequence."""
    if not tokens:
        return 0.0
    total = len(tokens)
    from collections import Counter
    counts = Counter(tokens)
    return -sum(
        (c / total) * math.log2(c / total)
        for c in counts.values()
        if c > 0
    )


def _repetition_score(content: str) -> float:
    """
    Fraction of tokens that appear more than once.
    High repetition → high score → hot.
    """
    if not content.strip():
        return 0.0
    if _enc is not None:
        token_ids = _enc.encode(content)
    else:
        token_ids = content.split()  # fallback: words
    if not token_ids:
        return 0.0
    from collections import Counter
    counts = Counter(token_ids)
    repeated = sum(c for c in counts.values() if c > 1)
    return min(repeated / len(token_ids), 1.0)


def _similarity_score(lines: list[str]) -> float:
    """
    Average Levenshtein similarity between consecutive non-empty lines.
    High similarity → repetitive → hot.
    """
    non_empty = [l for l in lines if l.strip()]
    if len(non_empty) < 2:
        return 0.0
    pairs = zip(non_empty, non_empty[1:])
    ratios = [_levenshtein_ratio(a, b) for a, b in pairs]
    return sum(ratios) / len(ratios)


def _entropy_score(lines: list[str]) -> float:
    """
    Average Shannon entropy over sliding windows of _ENTROPY_WINDOW lines.
    Low entropy → repetitive → HOT (so we invert: score = 1 - normalised_entropy).
    """
    if not lines:
        return 0.0

    window_entropies: list[float] = []
    for i in range(0, len(lines), _ENTROPY_WINDOW):
        window = '\n'.join(lines[i: i + _ENTROPY_WINDOW])
        if _enc is not None:
            tids = _enc.encode(window)
        else:
            tids = [hash(w) for w in window.split()]
        window_entropies.append(_shannon_entropy(tids))

    avg_entropy = sum(window_entropies) / len(window_entropies)
    # Normalise: typical code entropy is 3–8 bits/token.
    # We cap at 8 and invert so low entropy → high score.
    normalised = min(avg_entropy / 8.0, 1.0)
    return 1.0 - normalised


def _id_length_score(content: str) -> float:
    """
    Score based on average identifier length.
    Longer identifiers compress better → hot.
    """
    idents = re.findall(r'\b([A-Za-z_][A-Za-z0-9_]{2,})\b', content)
    if not idents:
        return 0.0
    avg_len = sum(len(i) for i in idents) / len(idents)
    # Normalise around threshold; clamp to [0, 1]
    score = (avg_len - _MIN_ID_LENGTH) / _MIN_ID_LENGTH
    return max(0.0, min(score, 1.0))


# ---------------------------------------------------------------------------
# Relationship extraction (Graphify-inspired)
# ---------------------------------------------------------------------------

def _extract_relationships(content: str, lang: str) -> tuple[list[str], list[str]]:
    """
    Extract import names and function call names from a code block.

    Returns:
        (block_imports, block_calls)
    """
    imports: list[str] = []
    calls:   list[str] = []

    # Try AST parsing for Python
    if lang in ('python', 'unknown'):
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                # Import statements
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.asname or alias.name)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imports.append(alias.asname or alias.name)
                # Function calls
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        calls.append(node.func.id)
                    elif isinstance(node.func, ast.Attribute):
                        calls.append(node.func.attr)
            return imports, calls
        except SyntaxError:
            pass  # fall through to regex

    # Regex fallback (JS, unknown, malformed Python)
    # Imports: import X / from X import / require('X') / import X from 'X'
    import_patterns = [
        r'^\s*import\s+([\w.]+)',
        r'^\s*from\s+([\w.]+)\s+import',
        r'require\([\'\"]([\w./]+)[\'\"]',
        r'import\s+\w+\s+from\s+[\'\"]([\w./]+)[\'\"]',
    ]
    for pat in import_patterns:
        imports.extend(re.findall(pat, content, re.MULTILINE))

    # Calls: word followed by (
    calls.extend(re.findall(r'\b([a-zA-Z_]\w*)\s*\(', content))

    # Deduplicate, preserve order
    seen: set[str] = set()
    unique_imports = [x for x in imports if not (x in seen or seen.add(x))]  # type: ignore[func-returns-value]
    seen.clear()
    unique_calls = [x for x in calls if not (x in seen or seen.add(x))]  # type: ignore[func-returns-value]

    return unique_imports, unique_calls


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_block(content: str, lang: str = 'unknown') -> HeatResult:
    """
    Scan a single block and return its HeatResult.

    Args:
        content: The (possibly minified) text of the block.
        lang:    Detected language string from Layer 0 / analyzer.py.

    Returns:
        HeatResult with hot_score, is_hot, dimension scores,
        and relationship signals.
    """
    if not content.strip():
        return HeatResult(
            hot_score=0.0, is_hot=False,
            entropy=0.0, repetition_score=0.0,
            similarity_score=0.0, id_length_score=0.0,
        )

    lines = content.split('\n')

    rep   = _repetition_score(content)
    sim   = _similarity_score(lines)
    ent   = _entropy_score(lines)
    idlen = _id_length_score(content)

    hot_score = (
        _W_REPETITION * rep
        + _W_SIMILARITY * sim
        + _W_ENTROPY    * ent
        + _W_ID_LENGTH  * idlen
    )
    hot_score = round(min(max(hot_score, 0.0), 1.0), 4)

    block_imports, block_calls = _extract_relationships(content, lang)

    return HeatResult(
        hot_score=hot_score,
        is_hot=hot_score >= HOT_THRESHOLD,
        entropy=round(ent, 4),
        repetition_score=round(rep, 4),
        similarity_score=round(sim, 4),
        id_length_score=round(idlen, 4),
        block_imports=block_imports,
        block_calls=block_calls,
    )


def scan_blocks(
    chunks: list[dict],
    lang: str = 'unknown',
) -> list[dict]:
    """
    Scan a list of chunk dicts (as produced by analyzer.chunk_text).
    Attaches heat metadata to each chunk and returns the enriched list.

    Conversation blocks are always marked cold — never compressed.

    Args:
        chunks: list of {'content': str, 'type': 'code'|'conv', ...}
        lang:   detected language

    Returns:
        Same list with each dict extended by:
            'heat': HeatResult
    """
    result = []
    for chunk in chunks:
        if chunk.get('type') == 'conv':
            # Conversation blocks are always cold
            heat = HeatResult(
                hot_score=0.0, is_hot=False,
                entropy=0.0, repetition_score=0.0,
                similarity_score=0.0, id_length_score=0.0,
            )
        else:
            heat = scan_block(chunk.get('content', ''), lang)

        result.append({**chunk, 'heat': heat})

    return result
