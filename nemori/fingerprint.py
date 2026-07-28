"""
fingerprint.py  —  Layer 2
SHA-256 fingerprint each chunk, then deterministically map
the hash bytes to a grid position using an LCG PRNG.

Same input ALWAYS → same hash → same grid position.

Upgrade (Phase 3+):
  fingerprint_chunk() now also returns 'raw_bytes' so that
  grid.py can reuse the same hash for force-directed seeding
  without recomputing SHA-256 a second time.
"""

import hashlib
import re
from collections import Counter


# ── LCG constants (same as glibc) ──────────────────────────────────────────
LCG_A = 1103515245
LCG_C = 12345
LCG_M = 2 ** 31


def _lcg(seed: int) -> int:
    return (LCG_A * seed + LCG_C) % LCG_M


def sha256_bytes(text: str) -> bytes:
    return hashlib.sha256(text.encode('utf-8')).digest()


def deterministic_pos(hash_bytes: bytes, grid_size: int, block_size: int) -> tuple[int, int]:
    """
    Use hash bytes [0-3] to seed an LCG, then pick a valid (row, col)
    within [0, grid_size - block_size].
    """
    seed = int.from_bytes(hash_bytes[0:4], 'big')
    max_pos = max(1, grid_size - block_size)

    seed = _lcg(seed)
    row = seed % (max_pos + 1)

    seed = _lcg(seed)
    col = seed % (max_pos + 1)

    return int(row), int(col)


def normalize(text: str) -> str:
    """Normalize for hashing: collapse whitespace, strip trailing spaces."""
    text = re.sub(r'[ \t]+', ' ', text)        # multiple spaces/tabs → single space
    text = re.sub(r'\n{2,}', '\n', text)        # multiple newlines → one
    return text.strip()


def get_raw_hash(content: str) -> bytes:
    """Return the raw SHA-256 bytes of normalised content.
    Used by grid.py to seed force-directed placement without
    recomputing the hash independently.
    """
    return sha256_bytes(normalize(content))


def fingerprint_chunk(content: str, grid_size: int, block_size: int) -> dict:
    """
    Returns:
        hash      — hex string (first 8 chars of SHA-256)
        grid_pos  — [row, col] deterministic position (LCG fallback)
        raw_bytes — full 32-byte SHA-256 digest (for grid.py seeding)
    """
    norm = normalize(content)
    raw_hash = sha256_bytes(norm)
    hex_hash = raw_hash.hex()[:8]
    row, col = deterministic_pos(raw_hash, grid_size, block_size)
    return {'hash': hex_hash, 'grid_pos': [row, col], 'raw_bytes': raw_hash}


# ── Minor pattern (blue block) detection ───────────────────────────────────

def extract_ngrams(text: str, n: int = 3) -> list[str]:
    """
    Extract word-level n-grams from text for pattern matching.
    Uses word-level n-grams (not character n-grams) to preserve semantic patterns.
    """
    words = re.findall(r'\b\w+\b', text.lower())
    if len(words) < n:
        return []
    return [' '.join(words[i:i+n]) for i in range(len(words) - n + 1)]


def find_repeated_substrings(text: str, min_len: int = 8, min_occurrences: int = 2) -> dict[str, int]:
    """
    Find repeated substrings in text using a rolling hash (Rabin-Karp).
    Returns dict of substring -> occurrence count for substrings >= min_len
    that occur at least min_occurrences times.
    """
    if len(text) < min_len:
        return {}
    
    # Use rolling hash (Rabin-Karp) to find repeated substrings
    base = 256
    mod = 2**61 - 1  # Large prime
    
    text_len = len(text)
    substr_count: dict[str, int] = defaultdict(int)
    
    # For each possible substring length from min_len to max_len
    max_len = min(len(text) // 2, 200)  # Cap at reasonable length
    
    for length in range(min_len, max_len + 1):
        if length > text_len:
            break
            
        # Rolling hash for this length
        hash_val = 0
        power = 1
        for i in range(length):
            hash_val = (hash_val * 256 + ord(text[i])) % (2**61 - 1)
            if i < length - 1:
                power = (power * 256) % (2**61 - 1)
        
        seen = {hash_val: 0}
        substr_count = defaultdict(int)
        substr_count[text[:length]] += 1
        
        for i in range(length, text_len):
            # Rolling hash update
            hash_val = (hash_val - ord(text[i - length]) * pow(256, length - 1, 2**61 - 1)) % (2**61 - 1)
            hash_val = (hash_val * 256 + ord(text[i])) % (2**61 - 1)
            
            # Verify match to handle collisions
            start = i - length + 1
            substr = text[start:start + length]
            substr_count[substr] += 1
        
        # Add to total counts
        for substr, count in substr_count.items():
            if count >= 2:
                substr_count[substr] = count
    
    # Filter by min_occurrences
    return {s: c for s, c in substr_count.items() if c >= 2}


def find_minor_patterns(chunks: list[dict], grid_size: int, min_freq: int = 2, pattern_map: dict[str, str] = None) -> list[dict]:
    """
    Find repeated n-gram patterns across all chunks.
    If pattern_map (ref_token -> text) is provided, blue blocks are generated
    EXACTLY for these entries by searching for marker tokens (§1, §2...) in chunk content.
    Otherwise, falls back to a legacy n-gram frequency scan.

    Each chunk dict needs: { 'content': str, 'grid_pos': [r, c], 'id': str }
    """
    if pattern_map is not None:
        minor_patterns = []
        # Sort pattern map entries by marker ID to ensure deterministic order (§1, §2, §3...)
        # Markers are like §1, §12 — we sort by the numeric part
        def get_pid(token: str) -> int:
            return int(token[1:]) if token[1:].isdigit() else 999
            
        sorted_patterns = sorted(pattern_map.items(), key=lambda x: get_pid(x[0]))
        
        for i, (ref_token, pattern_text) in enumerate(sorted_patterns):
            # Find which blocks contain this specific marker
            indices = [j for j, chunk in enumerate(chunks) if ref_token in chunk['content']]
            if not indices:
                continue  # Should not happen if pattern_map is correct

            raw_hash = sha256_bytes(pattern_text)
            hex_hash = raw_hash.hex()[:8]
            
            # Place at centroid of blocks containing the pattern
            # If it's a single block, it goes to that block's center
            avg_row = sum(chunks[idx].get('grid_pos', [0, 0])[0] for idx in indices) / len(indices)
            avg_col = sum(chunks[idx].get('grid_pos', [0, 0])[1] for idx in indices) / len(indices)
            
            row, col = int(avg_row), int(avg_col)
            block_ids = [chunks[idx].get('id', str(idx+1)) for idx in indices]

            minor_patterns.append({
                'id': f'm{i+1}',
                'pattern': pattern_text,
                'freq': len(indices),
                'hash': hex_hash,
                'grid_pos': [row, col],
                'connects_to': block_ids,
            })
        return minor_patterns

    # ── Legacy Fallback: n-gram frequency scan ───────────────────────────────
    ngram_chunks = {}
    for i, chunk in enumerate(chunks):
        content = chunk['content']
        ngrams = extract_ngrams(content, n=3) + extract_ngrams(content, n=4)
        for ng in set(ngrams):
            ngram_chunks.setdefault(ng, []).append(i)

    # Only patterns appearing in min_freq+ different chunks
    repeated = {gram: indices for gram, indices in ngram_chunks.items() if len(indices) >= min_freq}

    # Sort by frequency descending, cap at 15 minor blocks
    top = sorted(repeated.items(), key=lambda x: len(x[1]), reverse=True)[:15]

    minor_patterns = []
    for i, (pattern, indices) in enumerate(top):
        raw_hash = sha256_bytes(pattern)
        hex_hash = raw_hash.hex()[:8]
        
        avg_row = sum(chunks[idx].get('grid_pos', [0, 0])[0] for idx in indices) / len(indices)
        avg_col = sum(chunks[idx].get('grid_pos', [0, 0])[1] for idx in indices) / len(indices)
        
        row, col = int(avg_row), int(avg_col)

        block_ids = [chunks[idx].get('id', f'b{idx+1}') for idx in indices]
        minor_patterns.append({
            'id': f'm{i+1}',
            'pattern': pattern,
            'freq': len(indices),
            'hash': hex_hash,
            'grid_pos': [row, col],
            'connects_to': block_ids,
        })

    return minor_patterns
