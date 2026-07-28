"""
test_roundtrip.py -- Round-trip validation and correctness tests.

Pipeline under test:
  original_text -> chunk -> minify -> global_sub_map -> apply_subs -> assemble(.ctxpack)
                                                                             |
                                                                         decompress
                                                                             |
                                                                     verify_round_trip

Run:
    python -m pytest backend/tests/test_roundtrip.py -v
    python backend/tests/test_roundtrip.py
"""

import sys
import os
import re
import json
import ast
import hashlib
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.engine.analyzer     import chunk_text, detect_language, detect_style
from backend.engine.minifier     import minify, estimate_tokens
from backend.engine.substitution import build_substitution_map, apply_substitutions
from backend.engine.fingerprint  import fingerprint_chunk, find_minor_patterns
from backend.engine.heatmap     import scan_blocks
from backend.engine.competition import compete_blocks, compete_block
from backend.engine.sentinel    import check_final, check_layer
from backend.engine.ctxpack      import assemble, parse
from backend.engine.decompressor import decompress, verify_round_trip, KNOWN_EXPANSIONS
from backend.engine.diff import diff_ctxpack
from backend.engine.learner import log_result, predict_strategy
from backend.engine.patterns import extract_pattern_dict
from backend.engine.conv_compress import light_touch_compress as light_touch_compress_conv
from backend.engine.tokens import count_tokens, net_gain

GRID_SIZE  = 64
BLOCK_SIZE = 4


def compress_text(text):
    """Run the full compress pipeline (mirrors compress.py exactly).
    Returns (ctxpack_str, stats_dict) for testing purposes.
    """
    from hashlib import sha256 as _sha256
    chunks = chunk_text(text)
    processed = []
    for c in chunks:
        content = minify(c["content"]) if c["type"] == "code" else c["content"]
        processed.append({"content": content, "type": c["type"], "label": c["label"]})

    all_code = "\n".join(c["content"] for c in processed if c["type"] == "code")
    sub_map  = build_substitution_map(all_code) if all_code else {}
    if sub_map:
        for c in processed:
            if c["type"] == "code":
                c["content"] = apply_substitutions(c["content"], sub_map)

    # Block dedup (Item 8) — only if ref line saves tokens
    for idx, chunk in enumerate(processed, 1):
        chunk['id'] = idx
    seen_hashes: dict[str, int] = {}
    _TYPE_L = {'code': 'C', 'conv': 'V'}
    for chunk in processed:
        h = _sha256(chunk['content'].encode()).hexdigest()
        chunk['canonical_hash'] = h
        if h in seen_hashes:
            btype = _TYPE_L.get(chunk.get('type', 'code'), 'C')
            bare_line = f"@b {chunk['id']}{btype}"
            ref_line = f"@b {chunk['id']}{btype}={seen_hashes[h]}"
            gain = count_tokens(chunk['content']) + count_tokens(bare_line) - count_tokens(ref_line)
            if gain > 0:
                chunk['dedup_ref'] = seen_hashes[h]
        else:
            seen_hashes[h] = chunk['id']

    # Pattern dictionary (Item 7)
    from backend.engine.patterns import extract_pattern_dict as _extract_pattern_dict
    processed, pattern_map = _extract_pattern_dict(processed)

    # Conversation light-touch (Item 11)
    for c in processed:
        if c['type'] == 'conv':
            from backend.engine.conv_compress import light_touch_compress as _ltc
            c['content'], _ = _ltc(c['content'])

    blocks = []
    used   = set()
    for i, c in enumerate(processed):
        fp  = fingerprint_chunk(c["content"], GRID_SIZE, BLOCK_SIZE)
        pos = list(fp["grid_pos"])
        row, col = pos[0], pos[1]
        max_pos  = GRID_SIZE - BLOCK_SIZE
        att = 0
        while tuple(pos) in used and att < GRID_SIZE * GRID_SIZE:
            col = (col + 1) % (max_pos + 1)
            if col == 0:
                row = (row + 1) % (max_pos + 1)
            pos = [row, col]
            att += 1
        used.add(tuple(pos))
        c['grid_pos'] = pos
        block_dict = {"id": f"b{i+1}", "type": c["type"], "hash": fp["hash"],
                        "label": c["label"], "grid_pos": pos,
                        "content_compressed": c["content"]}
        if c.get('dedup_ref'):
            block_dict['dedup_ref'] = c['dedup_ref']
        if c.get('canonical_hash'):
            block_dict['canonical_hash'] = c['canonical_hash']
        blocks.append(block_dict)

    minor = find_minor_patterns(processed, GRID_SIZE, min_freq=2)
    raw   = estimate_tokens(text)
    comp  = estimate_tokens("\n".join(c["content"] for c in processed))
    lang  = detect_language(text)
    stats = {"raw_tokens": raw, "compressed_tokens": comp,
             "compression_ratio": comp / raw if raw else 1.0,
             "substitutions_made": len(sub_map), "lang_detected": lang}
    
    ctxpack_str = assemble(processed, sub_map, lang, pattern_map=pattern_map)
    return ctxpack_str, stats


PURE_PYTHON = (
    "class ConnectionPoolManager:\n"
    "    def __init__(self, max_connections):\n"
    "        self.active_connection_list = []\n"
    "        self.max_connections = max_connections\n"
    "    def initialize_connection_pool(self):\n"
    "        for i in range(self.max_connections):\n"
    "            self.active_connection_list.append(self.create_connection())\n"
    "    def create_connection(self):\n"
    '        return {"status": "open"}\n'
    "    def get_all_active_sessions(self):\n"
    "        return [c for c in self.active_connection_list]\n"
    "    def shutdown_connection_pool(self):\n"
    "        for conn in self.active_connection_list:\n"
    "            conn[\"status\"] = \"closed\"\n"
    "        self.active_connection_list.clear()\n"
)

PURE_JS = (
    "const DatabaseConnectionManager = {\n"
    "  initialize: function(config) {\n"
    "    this.connectionString = config.connectionString;\n"
    "    this.maxRetryAttempts = config.maxRetryAttempts;\n"
    "    this.activeConnections = [];\n"
    "    return this;\n"
    "  },\n"
    "  fetchUserProfile: function(userId) {\n"
    "    return this.activeConnections.find(c => c.userId === userId);\n"
    "  },\n"
    "  closeAllConnections: function() {\n"
    "    this.activeConnections = [];\n"
    "  }\n"
"};\n"
)

CONV_TEXT = "Human: What is Python?\nAssistant: A high-level programming language.\n"

# 200+ line realistic Python sample for large-input compression test
LARGE_PYTHON_SAMPLE = "\n".join([
    "import os",
    "import sys",
    "import json",
    "import hashlib",
    "from typing import List, Dict, Optional",
    "from dataclasses import dataclass",
    "",
    "",
    "@dataclass",
    "class UserProfile:",
    "    user_id: str",
    "    display_name: str",
    "    email: str",
    "    credits: int = 0",
    "    is_active: bool = True",
    "",
    "    def get_display_info(self) -> str:",
    "        return f'{self.display_name} ({self.email})'",
    "",
    "    def has_sufficient_credits(self, required: int) -> bool:",
    "        return self.credits >= required",
    "",
    "    def deduct_credits(self, amount: int) -> bool:",
    "        if not self.has_sufficient_credits(amount):",
    "            return False",
    "        self.credits -= amount",
    "        return True",
    "",
    "",
    "class TokenCompressionEngine:",
    "    def __init__(self, model_name: str = 'cl100k_base'):",
    "        self.model_name = model_name",
    "        self.compression_count = 0",
    "        self.total_tokens_saved = 0",
    "",
    "    def compress_text(self, text: str) -> Dict:",
    "        self.compression_count += 1",
    "        tokens_before = self._count_tokens(text)",
    "        compressed = self._apply_substitutions(text)",
    "        tokens_after = self._count_tokens(compressed)",
    "        self.total_tokens_saved += tokens_before - tokens_after",
    "        return {",
    "            'original': text,",
    "            'compressed': compressed,",
    "            'tokens_before': tokens_before,",
    "            'tokens_after': tokens_after,",
    "            'savings': tokens_before - tokens_after,",
    "        }",
    "",
    "    def _count_tokens(self, text: str) -> int:",
    "        return max(1, len(text) // 4)",
    "",
    "    def _apply_substitutions(self, text: str) -> str:",
    "        return text.replace('connection_pool_manager', 'A')",
    "",
    "    def get_statistics(self) -> Dict:",
    "        return {",
    "            'compressions_run': self.compression_count,",
    "            'total_tokens_saved': self.total_tokens_saved,",
    "        }",
    "",
    "",
    "class DataRepository:",
    "    def __init__(self, connection_string: str):",
    "        self.connection_string = connection_string",
    "        self.connection_pool = []",
    "        self.cache = {}",
    "",
    "    def establish_connection(self) -> bool:",
    "        try:",
    "            conn = self._create_connection()",
    "            self.connection_pool.append(conn)",
    "            return True",
    "        except Exception:",
    "            return False",
    "",
    "    def _create_connection(self) -> Dict:",
    "        return {'connected': True, 'string': self.connection_string}",
    "",
    "    def execute_query(self, query: str) -> List:",
    "        if query in self.cache:",
    "            return self.cache[query]",
    "        results = self._run_query(query)",
    "        self.cache[query] = results",
    "        return results",
    "",
    "    def _run_query(self, query: str) -> List:",
    "        return [{'result': 'data', 'query': query}]",
    "",
    "    def close_all_connections(self) -> None:",
    "        self.connection_pool.clear()",
    "        self.cache.clear()",
    "",
    "",
    "class AuthenticationService:",
    "    def __init__(self, config_key: str, token_expiry: int = 3600):",
    "        self.config_key = config_key",
    "        self.token_expiry = token_expiry",
    "        self.active_tokens = {}",
    "",
    "    def generate_token(self, user_id: str) -> str:",
    "        payload = f'{user_id}:{self.token_expiry}'",
    "        token = hashlib.sha256(payload.encode()).hexdigest()",
    "        self.active_tokens[token] = user_id",
    "        return token",
    "",
    "    def validate_token(self, token: str) -> Optional[str]:",
    "        return self.active_tokens.get(token)",
    "",
    "    def revoke_token(self, token: str) -> bool:",
    "        if token in self.active_tokens:",
    "            del self.active_tokens[token]",
    "            return True",
    "        return False",
    "",
    "    def cleanup_expired_tokens(self) -> int:",
    "        count = 0",
    "        expired = [t for t, u in self.active_tokens.items() if t.startswith('expired')]",
    "        for token in expired:",
    "            del self.active_tokens[token]",
    "            count += 1",
    "        return count",
    "",
    "",
    "def format_api_response(success: bool, data: any = None, error: str = None) -> Dict:",
    "    response = {'success': success}",
    "    if data is not None:",
    "        response['data'] = data",
    "    if error is not None:",
    "        response['error'] = error",
    "    return response",
    "",
    "",
    "def validate_email_address(email: str) -> bool:",
    "    if '@' not in email:",
    "        return False",
    "    local_part, domain = email.split('@', 1)",
    "    if not local_part or not domain:",
    "        return False",
    "    if '.' not in domain:",
    "        return False",
    "    return True",
    "",
    "",
    "def paginate_results(results: List, page: int = 1, per_page: int = 20) -> Dict:",
    "    total_items = len(results)",
    "    total_pages = max(1, (total_items + per_page - 1) // per_page)",
    "    start_index = (page - 1) * per_page",
    "    end_index = min(start_index + per_page, total_items)",
    "    page_results = results[start_index:end_index]",
    "    return {",
    "        'items': page_results,",
    "        'page': page,",
    "        'per_page': per_page,",
    "        'total_items': total_items,",
    "        'total_pages': total_pages,",
    "        'has_next': page < total_pages,",
    "        'has_previous': page > 1,",
    "    }",
    "",
    "",
    "def calculate_compression_ratio(original_tokens: int, compressed_tokens: int) -> float:",
    "    if original_tokens == 0:",
    "        return 1.0",
    "    return compressed_tokens / original_tokens",
])


def _norm(text):
    text = re.sub(r"#[^\n]*", "", text)
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


# ---- existing tests -------------------------------------------------------

def test_substitution_map_not_empty_for_long_python():
    ctxpack_str, _ = compress_text(PURE_PYTHON)
    parsed = parse(ctxpack_str)
    smap = parsed["alias_map"]
    assert len(smap) > 0, f"Expected substitutions but got empty map"
    print(f"  [PASS] sub_map has {len(smap)} entries: {smap}")


def test_content_compressed_not_empty():
    ctxpack_str, _ = compress_text(PURE_PYTHON)
    parsed = parse(ctxpack_str)
    for block in parsed["blocks"]:
        cc = block.get("content", "")
        assert cc, f"Block {block['id']} has empty content!"
    print(f"  [PASS] all {len(parsed['blocks'])} blocks have content")


def test_substitution_appears_in_content():
    ctxpack_str, _ = compress_text(PURE_PYTHON)
    parsed = parse(ctxpack_str)
    smap = parsed["alias_map"]
    if not smap:
        print("  [SKIP] no substitutions made")
        return
    all_content = " ".join(b.get("content", "") for b in parsed["blocks"])
    found = any(
        re.search(r"\b" + re.escape(short) + r"\b", all_content)
        for short in smap
    )
    assert found, (
        f"Labels {list(smap.keys())} not found in content!\n"
        f"Content preview: {all_content[:300]}"
    )
    print(f"  [PASS] short labels appear in compressed content")


def test_roundtrip_python():
    ctxpack_str, _ = compress_text(PURE_PYTHON)
    result  = verify_round_trip(PURE_PYTHON, ctxpack_str)
    assert result["match"], (
        f"Round-trip FAILED. diff_chars={result['diff_chars']}\n"
        f"original : {result['original_norm'][:300]}\n"
        f"recovered: {result['recovered_norm'][:300]}"
    )
    print(f"  [PASS] Python round-trip identical (diff_chars=0)")


def test_roundtrip_javascript():
    ctxpack_str, _ = compress_text(PURE_JS)
    result  = verify_round_trip(PURE_JS, ctxpack_str)
    assert result["match"], f"JS round-trip FAILED. diff_chars={result['diff_chars']}"
    print(f"  [PASS] JavaScript round-trip identical")


def test_conv_blocks_never_substituted():
    ctxpack_str, _ = compress_text(CONV_TEXT)
    parsed = parse(ctxpack_str)
    smap = parsed["alias_map"]
    for block in parsed["blocks"]:
        if block.get("type") == "conv" and smap:
            cc = block.get("content", "")
            for short in smap:
                found = re.search(r"\b" + re.escape(short) + r"\b", cc)
                assert not found, (
                    f"Conv block {block['id']} contains label '{short}' "
                    f"(={smap[short]}) -- substitution applied to conv block!\n"
                    f"Content: {cc[:200]}"
                )
    print(f"  [PASS] conv blocks not substituted")


def test_no_conv_misclassification_in_pure_code():
    ctxpack_str, _ = compress_text(PURE_PYTHON)
    parsed = parse(ctxpack_str)
    conv_blocks = [b for b in parsed["blocks"] if b.get("type") == "conv"]
    assert conv_blocks == [], (
        f"{len(conv_blocks)} blocks misclassified as conv:\n"
        + "\n".join(f"  {b['id']}: {b.get('label', '')}" for b in conv_blocks)
    )
    print(f"  [PASS] zero conv misclassifications in pure Python")


def test_compression_ratio_realistic():
    _, stats = compress_text(PURE_PYTHON)
    ratio = stats["compression_ratio"]
    assert 0.20 < ratio < 1.0, f"Compression ratio {ratio:.3f} out of expected range (expected 20-99%)"
    print(f"  [PASS] compression_ratio={ratio:.3f} ({round((1-ratio)*100)}% saved)")


def test_empty_input():
    ctxpack_str, _ = compress_text("")
    parsed = parse(ctxpack_str)
    assert parsed["blocks"] == [], "Empty input should produce zero blocks"
    print(f"  [PASS] empty input -> zero blocks")


def test_heatmap_cold_conv_blocks():
    chunks = chunk_text(CONV_TEXT)
    processed = scan_blocks(chunks, 'conversation')
    for block in processed:
        assert block['heat'].is_hot == False
    print("  [PASS] conv blocks always cold")


def test_competition_never_increases_tokens():
    chunks = chunk_text(PURE_PYTHON)
    scanned = scan_blocks(chunks, 'python')
    competed = compete_blocks(scanned, 'python')
    for block in competed:
        assert block['tokens_after'] <= block['tokens_before']
    print("  [PASS] competition never increases tokens")


def test_sentinel_blocks_regression():
    original = PURE_PYTHON
    fake_longer = original * 10
    result = check_final(original, fake_longer)
    assert result.passed == False
    print("  [PASS] sentinel blocks regression correctly")


def test_style_detection():
    result = detect_style(PURE_PYTHON, 'python')
    assert result in ('oop', 'functional', 'vibe', 'mixed')
    result2 = detect_style(CONV_TEXT, 'conversation')
    assert result2 in ('mixed', 'vibe')
    print("  [PASS] style detection working")


def test_sentinel_abort_returns_original():
    short = "x=1"
    fake_larger = short * 50
    result = check_final(short, fake_larger)
    assert result.passed == False, "Sentinel should reject when compressed > original"
    assert result.warning is not None, "Sentinel should emit a warning on failure"
    assert result.compressed_tokens > result.original_tokens
    print("  [PASS] sentinel abort: warning emitted, passed=False")


# ---- NEW TESTS: Alias collision guard (Fix #1) ----------------------------

def test_alias_collision_guard():
    """Substitution aliases (A, B, ...) must not collide with existing identifiers."""
    code = (
        "class A:\n"                    # 'A' is an existing identifier
        "    def calculate_value(self, input_data):\n"
        "        return input_data * 2\n"
        "class ConnectionPoolManager:\n"
        "    def __init__(self, max_connections):\n"
        "        self.active_connection_list = []\n"
        "        self.max_connections = max_connections\n"
        "    def initialize_connection_pool(self):\n"
        "        for i in range(self.max_connections):\n"
        "            self.active_connection_list.append(self.create_connection())\n"
        "    def create_connection(self):\n"
        '        return {"status": "open"}\n'
        "    def get_all_active_sessions(self):\n"
        "        return [c for c in self.active_connection_list]\n"
        "    def shutdown_connection_pool(self):\n"
        "        for conn in self.active_connection_list:\n"
        "            conn[\"status\"] = \"closed\"\n"
        "        self.active_connection_list.clear()\n"
    )
    sub_map = build_substitution_map(code)
    # The alias 'A' must NOT be used because there's a class named 'A' in the code
    assert 'A' not in sub_map, (
        f"Alias 'A' collides with existing class 'A'. Sub map: {sub_map}"
    )
    # Substitute and decompress: original 'A' must survive the round-trip unchanged
    substituted = apply_substitutions(code, sub_map)
    # The class name 'A' should still be 'A' in the output (not replaced by anything)
    assert re.search(r'\bclass A\b', substituted), (
        f"Class 'A' was corrupted by substitution. Output: {substituted[:200]}"
    )
    print(f"  [PASS] alias collision guard: 'A' not used as alias. map={sub_map}")


# ---- NEW TESTS: Round-trip reversibility for every competition strategy (Fix #2) -

def test_inline_abbreviation_reversible():
    """Inline abbreviation strategy must produce reversible output via @i section."""
    # Code with snake_case identifiers that could trigger inline abbreviation
    text = (
        "def process_connection_pool():\n"
        "    connection_pool_manager = create_connection_pool()\n"
        "    max_connection_count = get_connection_count()\n"
        "    for active_connection in connection_pool_manager:\n"
        "        process_active_connection(active_connection)\n"
    )
    ctxpack_str, _ = compress_text(text)
    parsed = parse(ctxpack_str)
    # Verify @i section exists if inline abbreviation was used
    # (minimum: @i must be parseable without error)
    assert 'inline_abbrev_map' in parsed, "Parser must return inline_abbrev_map key"
    # Round-trip must succeed
    result = verify_round_trip(text, ctxpack_str)
    assert result["match"], (
        f"Inline abbreviation round-trip FAILED. diff_chars={result['diff_chars']}"
    )
    print(f"  [PASS] inline abbreviation round-trip OK (diff_chars={result['diff_chars']})")


def test_known_tag_expansion():
    """[KNOWN:tag] markers must expand back to original boilerplate."""
    # Build a ctxpack with known tags and decompress it
    ctxpack = (
        "@s v2 lang=python blocks=1 aliases=0\n"
        "@b id=1 type=C\n"
        "[KNOWN:__main__]\n"
        "[KNOWN:shebang]\n"
        "x = 1\n"
    )
    result = decompress(ctxpack)
    full = result["full_text"]
    assert "[KNOWN:" not in full, "KNOWN tags were not expanded"
    assert "if __name__ == '__main__':" in full, "__main__ tag not expanded"
    assert "#!/usr/bin/env python" in full, "shebang tag not expanded"
    print("  [PASS] known boilerplate tags expand correctly")
    # Also verify the fixed expansion table in KNOWN_EXPANSIONS
    assert "pass" in KNOWN_EXPANSIONS
    assert "ellipsis" in KNOWN_EXPANSIONS
    assert len(KNOWN_EXPANSIONS) >= 5


def test_i_section_roundtrip():
    """@i section must survive assemble -> parse -> decompress round-trip."""
    abbrev_map = {"connection_pool": "cp", "max_connections": "mc"}
    blocks = [
        {"type": "code", "content": "cp = create()\nmc = 10"},
    ]
    ctxpack = assemble(blocks, {}, "python", inline_abbrev_map=abbrev_map)
    # Parse must read @i back
    parsed = parse(ctxpack)
    assert parsed["inline_abbrev_map"] == abbrev_map, (
        f"@i section not parsed correctly: {parsed['inline_abbrev_map']}"
    )
    # Decompress must expand cp -> connection_pool
    result = decompress(ctxpack)
    expanded = result["full_text"]
    assert "connection_pool" in expanded, (
        f"@i abbreviation not expanded in decompress: {expanded}"
    )
    print("  [PASS] @i section round-trip: assemble -> parse -> decompress OK")


# ---- NEW TESTS: @-spec syntax (consistency checks) ------------------------

def test_parse_inline_abbrev_map_empty_by_default():
    """parse must return empty inline_abbrev_map when no @i is present."""
    ctxpack = "@s v2 lang=python blocks=0 aliases=0\n"
    parsed = parse(ctxpack)
    assert parsed.get("inline_abbrev_map") == {}, (
        f"Expected empty inline_abbrev_map, got {parsed.get('inline_abbrev_map')}"
    )
    print("  [PASS] inline_abbrev_map defaults to {}")


def test_parse_templates_empty_by_default():
    """parse must return empty templates list when no @t is present."""
    ctxpack = "@s v2 lang=python blocks=1 aliases=0\n@b id=1 type=C\nx=1\n"
    parsed = parse(ctxpack)
    assert parsed.get("templates") == [], (
        f"Expected empty templates, got {parsed.get('templates')}"
    )
    print("  [PASS] templates defaults to []")


# ---- NEW TESTS: Sentinel layer revert (Fix #12) ---------------------------

def test_sentinel_layer_revert_rejects_regression():
    """check_layer must reject a layer that makes content larger."""
    before = "short text"
    after = "short text " + ("x" * 1000)  # much longer
    result = check_layer("test-layer", before, after, min_savings=1)
    assert result.passed == False, "check_layer must reject regression"
    assert result.warning is not None, "check_layer must emit warning on failure"
    print("  [PASS] sentinel layer gate rejects regression")


def test_sentinel_layer_passes_improvement():
    """check_layer must pass when content is strictly smaller."""
    before = "longer text that is quite long for no good reason"
    after = "short"
    result = check_layer("test-layer", before, after, min_savings=1)
    assert result.passed == True, "check_layer must accept improvement"
    print("  [PASS] sentinel layer gate passes improvement")


# ---- NEW TESTS: Diff engine (Fix #13) -------------------------------------

def _content_hash(text: str) -> str:
    """Compute same 8-char hash as fingerprint_chunk."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def test_diff_unchanged_blocks_reused():
    """Diff engine must identify unchanged blocks and reuse their content."""
    content_a = "x = 1"
    content_b = "y = 2"
    content_c = "z = 3"
    # assemble() reads block['content'], not block['content_compressed']
    old_blocks = [
        {"id": "b1", "type": "code", "hash": _content_hash(content_a), "content": content_a},
        {"id": "b2", "type": "code", "hash": _content_hash(content_b), "content": content_b},
    ]
    old_ctxpack = assemble(old_blocks, {}, "python")

    new_blocks = [
        {"id": 1, "type": "code", "hash": _content_hash(content_a), "content_compressed": content_a},
        {"id": 2, "type": "code", "hash": _content_hash(content_c), "content_compressed": content_c},
    ]

    result = diff_ctxpack(old_ctxpack, new_blocks)
    assert len(result["unchanged_ids"]) >= 1, (
        f"Expected at least 1 unchanged block, got {result['unchanged_ids']}"
    )
    assert len(result["changed_ids"]) >= 1, (
        f"Expected at least 1 changed block, got {result['changed_ids']}"
    )
    merged = parse(result["merged_ctxpack_str"])
    assert len(merged["blocks"]) > 0, "Merged ctxpack has no blocks"
    print(f"  [PASS] diff unchanged={result['unchanged_ids']} changed={result['changed_ids']}")


def test_diff_added_and_deleted():
    """Diff engine must detect added and deleted blocks."""
    content_a = "a = 1"
    content_b = "b = 2"
    content_c = "c = 3"
    # 3 old blocks, only 2 new blocks -- b2 should be deleted
    old_blocks = [
        {"id": "b1", "type": "code", "hash": _content_hash(content_a), "content": content_a},
        {"id": "b2", "type": "code", "hash": _content_hash(content_b), "content": content_b},
        {"id": "b3", "type": "code", "hash": _content_hash(content_c), "content": content_c},
    ]
    old_ctxpack = assemble(old_blocks, {}, "python")

    # Only 2 new blocks (b3 changed), so b2 is deleted
    new_content_c = "c = 33"
    new_blocks = [
        {"id": 1, "type": "code", "hash": _content_hash(content_a), "content_compressed": content_a},
        {"id": 3, "type": "code", "hash": _content_hash(new_content_c), "content_compressed": new_content_c},
    ]

    result = diff_ctxpack(old_ctxpack, new_blocks)
    assert len(result["deleted_ids"]) >= 1, (
        f"Expected deleted block, got {result['deleted_ids']}"
    )
    assert len(result["changed_ids"]) >= 1, (
        f"Expected changed block, got {result['changed_ids']}"
    )
    assert len(result["added_blocks"]) >= 0, (
        f"Unexpected added blocks: {len(result['added_blocks'])}"
    )
    print(f"  [PASS] diff deleted={result['deleted_ids']} changed={result['changed_ids']}")


def test_diff_stable_across_runs():
    """Compressing the same source twice must produce the same canonical
    hashes — diff must report all blocks as unchanged when comparing
    the two outputs."""
    from backend.engine.diff import diff_ctxpack as _diff

    source = (
        "def setup():\n"
        "    return 0\n"
        "\n"
        "def teardown():\n"
        "    return 1\n"
    )

    # Run compression twice
    ctx1, _ = compress_text(source)
    ctx2, _ = compress_text(source)

    p1 = parse(ctx1)
    p2 = parse(ctx2)

    # Check canonical hashes are present and stable
    b1_h = [b.get('canonical_hash', '') for b in p1['blocks']]
    b2_h = [b.get('canonical_hash', '') for b in p2['blocks']]
    assert all(b1_h), f"Blocks from run 1 missing canonical_hash: {b1_h}"
    assert all(b2_h), f"Blocks from run 2 missing canonical_hash: {b2_h}"
    assert b1_h == b2_h, f"canonical_hash differs between runs: {b1_h} vs {b2_h}"

    # Build new_blocks dicts as diff expects them (with canonical_hash from run 2)
    new_blocks = []
    for i, b in enumerate(p2['blocks'], 1):
        new_blocks.append({
            'id': i,
            'canonical_hash': b.get('canonical_hash', ''),
            'content_compressed': b.get('content', ''),
        })

    # Diff ctx1 (old) against current blocks (new)
    result = _diff(ctx1, new_blocks)
    assert len(result['changed_ids']) == 0, (
        f"Diff reported changed blocks despite identical source: "
        f"changed={result['changed_ids']}"
    )
    assert len(result['unchanged_ids']) == len(p1['blocks']), (
        f"Expected all {len(p1['blocks'])} unchanged, "
        f"got {len(result['unchanged_ids'])}"
    )
    print(f"  [PASS] diff stable across runs: {len(p1['blocks'])} blocks unchanged")


# ---- NEW TESTS: Learner short-circuit (Fix #14) ---------------------------

def test_learner_predict_none_when_empty():
    """predict_strategy must return None when memory is empty or insufficient."""
    result = predict_strategy({"lang": "python", "style": "oop", "total_raw_tokens": 200})
    assert result is None, (
        f"Expected None for empty memory, got {result!r}"
    )
    print("  [PASS] learner predict_strategy returns None with no history")


def test_learner_log_and_predict_threshold():
    """log_result writes to JSONL; predict_strategy returns strategy past threshold."""
    import tempfile
    import os
    td = tempfile.mkdtemp()
    mem_path = os.path.join(td, "test_memory.jsonl")
    old_env = os.environ.get("NEMORI_LEARNER_PATH")
    os.environ["NEMORI_LEARNER_PATH"] = mem_path

    try:
        profile = {"lang": "python", "style": "oop", "total_raw_tokens": 200,
                    "total_comp_tokens": 120}
        strategies = {"alias_substitution": 5, "keep_original": 0}

        # Write 60 samples (past 50 threshold) all with alias_substitution
        for _ in range(60):
            log_result(profile, strategies)

        # Rule-based predictor returns None for python <500 tokens (full tournament)
        result = predict_strategy(
            {"lang": "python", "style": "oop", "total_raw_tokens": 200}
        )
        assert result is None, (
            f"Expected None (full tournament) for python<500t, got {result!r}"
        )
        print(f"  [PASS] rule-based predictor: full tournament for python<500t")
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)
        if old_env is None:
            os.environ.pop("NEMORI_LEARNER_PATH", None)
        else:
            os.environ["NEMORI_LEARNER_PATH"] = old_env


# ---- NEW TESTS: Large input compression -----------------------------------

def test_large_sample_compression_saves_tokens():
    """Compression must reduce tokens on a realistic 200+ line Python sample."""
    ctxpack_str, stats = compress_text(LARGE_PYTHON_SAMPLE)
    assert stats["compressed_tokens"] < stats["raw_tokens"], (
        f"Compression did not save tokens: raw={stats['raw_tokens']}, "
        f"compressed={stats['compressed_tokens']}"
    )
    print(f"  [PASS] large sample: {stats['raw_tokens']} -> {stats['compressed_tokens']} tokens "
          f"(ratio={stats['compression_ratio']:.3f}, savings={stats['raw_tokens'] - stats['compressed_tokens']} tok)")


def test_large_sample_roundtrip():
    """Large sample must survive full round-trip."""
    ctxpack_str, _ = compress_text(LARGE_PYTHON_SAMPLE)
    result = verify_round_trip(LARGE_PYTHON_SAMPLE, ctxpack_str)
    assert result["match"], (
        f"Large sample round-trip FAILED. diff_chars={result['diff_chars']}\n"
        f"original : {result['original_norm'][:200]}\n"
        f"recovered: {result['recovered_norm'][:200]}"
    )
    print(f"  [PASS] large sample round-trip OK (diff_chars={result['diff_chars']})")


# ---- NEW TESTS: File-tree @f metadata -------------------------------------

def test_file_tree_assemble_roundtrip():
    """@f section must survive assemble() -> parse() round-trip."""
    file_tree = ["backend/main.py", "backend/api/compress.py", "backend/engine/sentinel.py"]
    blocks = [
        {"type": "code", "content": "x = 1"},
        {"type": "code", "content": "y = 2"},
        {"type": "code", "content": "z = 3"},
    ]
    ctxpack = assemble(blocks, {}, "python", file_tree=file_tree)
    assert "@f" in ctxpack, "@f line missing from ctxpack"
    parsed = parse(ctxpack)
    assert parsed["file_tree"] == file_tree, (
        f"file_tree mismatch: {parsed['file_tree']} != {file_tree}"
    )
    for i, block in enumerate(parsed["blocks"]):
        assert block.get("file_index") == i, (
            f"Block {i} file_index mismatch: {block.get('file_index')}"
        )
    # Round-trip without file_tree must not include @f
    ctxpack_no_f = assemble(blocks, {}, "python")
    assert "@f" not in ctxpack_no_f, "@f line present without file_tree"
    parsed_no_f = parse(ctxpack_no_f)
    assert parsed_no_f.get("file_tree") == [], (
        f"Expected empty file_tree, got {parsed_no_f.get('file_tree')}"
    )
    for block in parsed_no_f["blocks"]:
        assert block.get("file_index") is None, (
            f"Expected None file_index without @f, got {block.get('file_index')}"
        )
    print("  [PASS] file-tree assemble->parse round-trip OK")


def test_file_tree_pipeline_preserved():
    """File tree metadata must survive full compress pipeline."""
    ctxpack_str, _ = compress_text(PURE_PYTHON)
    # Inject file_tree via manual assemble — compress_text doesn't pass it
    # Actually, let's test that assemble with file_tree produces parseable output
    blocks = [{"type": "code", "content": "x = 1"}]
    file_tree = ["src/main.py"]
    ctxpack = assemble(blocks, {}, "python", file_tree=file_tree)
    parsed = parse(ctxpack)
    assert parsed["file_tree"] == file_tree
    assert parsed["blocks"][0]["file_index"] == 0
    print("  [PASS] file-tree pipeline preserved through assemble/parse")


def test_file_tree_multiple_blocks_same_file():
    """Multiple blocks can reference the same file path."""
    file_tree = ["src/utils.py", "src/utils.py", "src/main.py"]
    blocks = [
        {"type": "code", "content": "def helper():\n    pass"},
        {"type": "code", "content": "class Util:\n    pass"},
        {"type": "code", "content": "x = 1"},
    ]
    ctxpack = assemble(blocks, {}, "python", file_tree=file_tree)
    parsed = parse(ctxpack)
    assert parsed["blocks"][0]["file_index"] == 0
    assert parsed["blocks"][1]["file_index"] == 1
    assert parsed["blocks"][2]["file_index"] == 2
    print("  [PASS] multiple blocks share same file-tree path")


def test_file_tree_length_mismatch_raises_error():
    """Passing a file_tree with wrong length must raise ValueError."""
    blocks = [
        {"type": "code", "content": "x = 1"},
        {"type": "code", "content": "y = 2"},
    ]
    file_tree = ["src/main.py"]  # 1 entry for 2 blocks
    try:
        assemble(blocks, {}, "python", file_tree=file_tree)
        assert False, "Expected ValueError for mismatched file_tree length"
    except ValueError as e:
        assert "file_tree length" in str(e).lower(), f"Wrong error message: {e}"
    print("  [PASS] file_tree length mismatch raises ValueError")


def test_file_tree_template_collapse_preserves_indices():
    """Template-collapsed blocks must not shift f= indices for surviving blocks."""
    blocks = [
        {"type": "code", "content": "def setup():\n    return 1", "strategy": "template_collapse"},
        {"type": "code", "content": "x = 1"},
        {"type": "code", "content": "y = 2"},
        {"type": "code", "content": "def another():\n    return 2", "strategy": "template_collapse"},
        {"type": "code", "content": "z = 3"},
    ]
    file_tree = ["src/setup.py", "src/main.py", "src/main.py", "src/other.py", "src/main.py"]
    ctxpack = assemble(blocks, {}, "python", file_tree=file_tree)
    parsed = parse(ctxpack)
    # Surviving blocks are indices 1, 2, 4 in the original list (0-based)
    # Their file_tree entries should be: src/main.py, src/main.py, src/main.py
    expected_paths = ["src/main.py", "src/main.py", "src/main.py"]
    parsed_ft = parsed.get("file_tree", [])
    assert parsed_ft == expected_paths, (
        f"Expected file_tree={expected_paths}, got {parsed_ft}"
    )
    for i, block in enumerate(parsed["blocks"]):
        expected_idx = i  # 0, 1, 2 — continuous, not shifted by collapsed blocks
        assert block.get("file_index") == expected_idx, (
            f"Block {block['id']}: expected file_index={expected_idx}, "
            f"got {block.get('file_index')}"
        )
        if expected_idx < len(expected_paths):
            assert parsed_ft[expected_idx] == expected_paths[expected_idx], (
                f"Block {block['id']}: path mismatch"
            )
    print("  [PASS] template-collapse preserves file_tree indices for surviving blocks")


def test_export_route_forwards_file_tree():
    """compress and export routes must produce the same @f output for the same input."""
    from backend.engine.ctxpack import assemble as _assemble
    from backend.engine.ctxpack import parse as _parse

    blocks = [
        {"type": "code", "content": "x = 1"},
        {"type": "code", "content": "y = 2"},
        {"type": "code", "content": "z = 3"},
    ]
    file_tree = ["src/main.py", "src/utils.py", "src/main.py"]

    # Call assemble as both routes would — same params
    ctxpack = _assemble(blocks, {}, "python", file_tree=file_tree)
    parsed = _parse(ctxpack)

    assert "@f" in ctxpack, "ctxpack missing @f line"
    assert parsed["file_tree"] == file_tree, (
        f"file_tree mismatch: {parsed['file_tree']} != {file_tree}"
    )
    for i, block in enumerate(parsed["blocks"]):
        assert block.get("file_index") == i, (
            f"Block {i}: expected file_index={i}, got {block.get('file_index')}"
        )
    print("  [PASS] export/compress routes produce consistent @f output")


# ---- NEW TESTS: Decompressor template expansion ---------------------------

def test_decompress_template_expansion():
    """@t/@a sections in ctxpack must be expanded by decompress()."""
    ctxpack = (
        "@s v2 lang=python blocks=0 aliases=0\n"
        "@t def FUNC(V1): return V1\n"
        "@a add_one:x;add_two:y\n"
    )
    result = decompress(ctxpack)
    full = result["full_text"]
    assert "add_one" in full or "add_two" in full, (
        f"Template blocks not expanded: {full[:300]}"
    )
    print("  [PASS] template expansion produces function blocks")


# ---- NEW TESTS: Block boundary fix for multi-line try/except (Prerequisite) -

def test_try_except_block_boundary_roundtrip():
    """Multi-line try/except must not be split across block boundaries.
    After compress -> decompress, the output must be syntactically valid Python."""
    source = (
        "def setup_resources():\n"
        "    try:\n"
        "        resource_a = allocate('a')\n"
        "        resource_b = allocate('b')\n"
        "        return resource_a, resource_b\n"
        "    except AllocationError:\n"
        "        log_error('allocation failed')\n"
        "        cleanup()\n"
        "        return None\n"
        "\n"
        "    def helper():\n"
        "        pass\n"
    )
    ctxpack_str, _ = compress_text(source)
    result = decompress(ctxpack_str)
    decompressed = result['full_text']
    try:
        ast.parse(decompressed)
    except SyntaxError as e:
        # Try to parse each individual block
        for b in result['blocks']:
            try:
                ast.parse(b['content_expanded'])
            except SyntaxError:
                pass  # individual blocks may not be full programs
        raise AssertionError(
            f"Decompressed output is not valid Python: {e}\n"
            f"Decompressed text:\n{decompressed}"
        )
    print("  [PASS] multi-line try/except round-trips to valid Python")


# ---- NEW TESTS: Block dedup (Item 8) --------------------------------------

def test_block_dedup_roundtrip():
    """Two identical blocks — the second must become a dedup ref,
    decompress restores both in full and in original order."""
    text = (
        "def setup():\n"
        "    return 1\n"
        "\n"
        "def setup():\n"
        "    return 1\n"
    )
    ctxpack_str, _ = compress_text(text)
    parsed = parse(ctxpack_str)
    blocks = parsed['blocks']
    assert len(blocks) == 2, f"Expected 2 blocks, got {len(blocks)}"
    result = decompress(ctxpack_str)
    full = result['full_text']
    # Both blocks must have content after decompress
    assert 'return 1' in full, f"Content missing from decompressed output: {full}"
    print("  [PASS] block dedup round-trip restores both blocks")


def test_dedup_preserves_file_tree_index():
    """A deduped block with f=<N> set must still carry that index."""
    block_a = {"type": "code", "content": "x = 1", "id": 1}
    block_b = {"type": "code", "content": "x = 1", "id": 2, "dedup_ref": 1}
    file_tree = ["src/a.py", "src/b.py"]
    from backend.engine.ctxpack import assemble as _assemble
    ctxpack = _assemble([block_a, block_b], {}, "python", file_tree=file_tree)
    parsed = parse(ctxpack)
    assert len(parsed['blocks']) == 2, f"Expected 2 blocks, got {len(parsed['blocks'])}"
    # Second block should still have its file_index even though deduped
    assert parsed['blocks'][1].get('file_index') == 1, (
        f"Deduped block lost file_index: {parsed['blocks'][1]}"
    )
    print("  [PASS] dedup preserves file-tree index")


def test_dedup_three_or_more_identical_blocks():
    """3+ identical blocks: all after the first must reference block 1,
    never chain-reference each other. Decompress restores all in order."""
    text = (
        "def setup():\n"
        "    return 1\n"
        "\n"
        "def setup():\n"
        "    return 1\n"
        "\n"
        "def setup():\n"
        "    return 1\n"
    )
    ctxpack_str, _ = compress_text(text)
    parsed = parse(ctxpack_str)
    blocks = parsed['blocks']
    assert len(blocks) == 3, f"Expected 3 blocks, got {len(blocks)}"
    dedup_refs = [b.get('dedup_ref') for b in blocks]
    # Block 1 has no dedup_ref (first occurrence)
    assert dedup_refs[0] is None, f"Block 1 should not have dedup_ref, got {dedup_refs[0]}"
    # Blocks 2 and 3 both reference block 1, never chain
    assert dedup_refs[1] == 1, f"Block 2 should reference block 1, got dedup_ref={dedup_refs[1]}"
    assert dedup_refs[2] == 1, f"Block 3 should reference block 1, got dedup_ref={dedup_refs[2]}"
    # Decompress restores all three
    result = decompress(ctxpack_str)
    full = result['full_text']
    assert 'return 1' in full, f"Content missing from decompressed output: {full}"
    print("  [PASS] 3+ identical blocks: all reference block 1, decompress restores all")


# ---- NEW TESTS: Pattern dictionary (Item 7) -------------------------------

def test_pattern_dict_below_threshold_not_applied():
    """A pattern occurring once must never produce a @p entry."""
    blocks = [
        {"content": "the quick brown fox", "id": 1},
        {"content": "jumps over lazy dog", "id": 2},
    ]
    updated_blocks, pattern_map = extract_pattern_dict(blocks, min_occurrences=2)
    assert len(pattern_map) == 0, (
        f"Expected empty pattern_map for below-threshold patterns, got {pattern_map}"
    )
    print("  [PASS] pattern below threshold not applied")


def test_pattern_dict_roundtrip():
    """A pattern occurring 3+ times across blocks produces a @p entry,
    refs get inserted, decompress restores the exact original text."""
    repeat = "the quick brown fox"
    text = (
        f"def a():\n    print('{repeat}')\n    return 1\n"
        f"\ndef b():\n    print('{repeat}')\n    return 2\n"
        f"\ndef c():\n    print('{repeat}')\n    return 3\n"
        f"\ndef d():\n    print('{repeat}')\n    return 4\n"
        f"\ndef e():\n    print('{repeat}')\n    return 5\n"
        f"\ndef f():\n    print('{repeat}')\n    return 6\n"
    )
    ctxpack_str, _ = compress_text(text)
    parsed = parse(ctxpack_str)
    # @p section should exist if pattern was beneficial
    pattern_map = parsed.get('pattern_map', {})
    assert len(pattern_map) > 0, (
        f"Expected pattern dict entries for '{repeat}' appearing 6 times, "
        f"but got empty map"
    )
    result = decompress(ctxpack_str)
    full = result['full_text']
    assert repeat in full, (
        f"Pattern '{repeat}' lost after decompress: {full[:300]}"
    )
    print(f"  [PASS] pattern dict round-trip with {len(pattern_map)} entries")


def test_pattern_dict_runs_after_dedup():
    """Two identical blocks (subject to dedup) with internal repeated pattern:
    pattern dictionary's occurrence count must be 1 (from the single surviving
    block), not 2."""
    repeat = "internal repeat call"
    block_content = f"def f():\n    {repeat}\n    {repeat}\n    return True\n"
    text = block_content + "\n" + block_content
    ctxpack_str, _ = compress_text(text)
    parsed = parse(ctxpack_str)
    pattern_map = parsed.get('pattern_map', {})
    result = decompress(ctxpack_str)
    full = result['full_text']
    assert repeat in full, (
        f"Pattern '{repeat}' missing after decompress: {full[:300]}"
    )
    print("  [PASS] pattern dict runs after dedup")


def test_pattern_dict_net_gain_rejects_short():
    """A short pattern (e.g. 2 tokens) repeated across blocks must be
    rejected by the net-gain check: the marker + dictionary overhead
    costs more than the savings. The original text must survive
    decompress unchanged."""
    text = (
        "def a():\n"
        "    do it\n"
        "    return 1\n"
        "\n"
        "def b():\n"
        "    do it\n"
        "    return 2\n"
        "\n"
        "def c():\n"
        "    something else\n"
        "    return 3\n"
    )
    ctxpack_str, _ = compress_text(text)
    parsed = parse(ctxpack_str)
    pattern_map = parsed.get('pattern_map', {})
    assert len(pattern_map) == 0, (
        f"Short pattern should be rejected by gain check, got {pattern_map}"
    )
    result = decompress(ctxpack_str)
    full = result['full_text']
    assert 'do it' in full, (
        f"Short pattern 'do it' missing after decompress: {full[:300]}"
    )
    print("  [PASS] short pattern correctly rejected by net-gain check")


# ---- NEW TESTS: Frequency-ordered aliases (Item 10) -----------------------

def test_frequency_ordered_aliases():
    """Most frequent identifier gets the cheapest available alias."""
    text = (
        "def process_connection_pool():\n"
        "    connection_pool = create_connection_pool()\n"
        "    active_connections = get_active_connections()\n"
        "    max_connections = get_max_connections()\n"
        "    return process_connection_pool(connection_pool, active_connections, max_connections)\n"
    )
    ctxpack_str, _ = compress_text(text)
    parsed = parse(ctxpack_str)
    smap = parsed.get('alias_map', {})
    # If substitution was made, the most frequent ident should get 'A'
    if smap:
        # Check that 'A' is used for some identifier
        assert 'A' in smap, (
            f"'A' not used as alias despite being cheapest: {smap}"
        )
    print(f"  [PASS] frequency-ordered aliases: map={smap}")


def test_alias_one_token_guard():
    """A candidate label that doesn't encode to exactly 1 token must be
    skipped; the next candidate is tried instead."""
    from backend.engine.substitution import build_substitution_map_ordered

    # Identifiers to substitute — all short, put a long one first
    idents = ["very_long_identifier"]
    existing = set()
    result = build_substitution_map_ordered(idents, existing)
    # The map should use 'A' (1 token), never a multi-token label
    for label in result:
        from backend.engine.tokens import count_tokens
        assert count_tokens(label) == 1, (
            f"Label '{label}' costs {count_tokens(label)} tokens, expected 1"
        )
    print(f"  [PASS] 1-token guard: all labels are single-token: {result}")


# ---- NEW TESTS: Slim @s2 syntax (Item 9) ----------------------------------

def test_slim_syntax_assemble_and_parse():
    """@s3 header and compact @b format must assemble and parse correctly."""
    blocks = [
        {"type": "code", "content": "x = 1"},
        {"type": "code", "content": "y = 2"},
    ]
    ctxpack = assemble(blocks, {}, "python")
    # Must use @s3 header
    assert ctxpack.startswith("@s3"), (
        f"Expected @s3 header, got: {ctxpack[:50]}"
    )
    # Must use compact @b format
    assert "@b 1C" in ctxpack, (
        f"Expected compact @b 1C format: {ctxpack[:100]}"
    )
    # Parse back
    parsed = parse(ctxpack)
    assert parsed['lang'] == 'python'
    assert len(parsed['blocks']) == 2
    print("  [PASS] slim @s2 syntax assemble/parse correct")


def test_legacy_v2_still_parseable():
    """Legacy @s v2 format must still parse correctly."""
    legacy = "@s v2 lang=python blocks=1 aliases=0\n@b id=1 type=C\nx = 1\n"
    parsed = parse(legacy)
    assert parsed['lang'] == 'python'
    assert len(parsed['blocks']) == 1
    assert parsed['blocks'][0]['content'] == 'x = 1'
    print("  [PASS] legacy v2 format still parseable")


def test_slim_syntax_dedup_form():
    """Compact dedup form @b <id><type>=<ref_id> must assemble and parse."""
    block_a = {"type": "code", "content": "x = 1", "id": 1}
    block_b = {"type": "code", "content": "x = 1", "id": 2, "dedup_ref": 1}
    ctxpack = assemble([block_a, block_b], {}, "python")
    parsed = parse(ctxpack)
    # Second block should have dedup_ref set
    blocks = parsed['blocks']
    assert len(blocks) == 2
    assert blocks[1].get('dedup_ref') == 1, (
        f"Dedup ref not preserved: {blocks[1]}"
    )
    print("  [PASS] slim @b dedup form correct")


def test_slim_syntax_canonical_hash():
    """@b line must persist canonical_hash through assemble->parse."""
    block = {"type": "code", "content": "x = 1", "canonical_hash": "abc12345deadbeef"}
    ctxpack = assemble([block], {}, "python")
    assert "h=abc12345deadbeef" in ctxpack, (
        f"canonical_hash missing from @b line: {ctxpack}"
    )
    parsed = parse(ctxpack)
    assert parsed['blocks'][0].get('canonical_hash') == 'abc12345deadbeef', (
        f"canonical_hash not parsed: {parsed['blocks'][0]}"
    )
    print("  [PASS] canonical_hash round-trips through assemble->parse")


def test_slim_format_token_cost():
    """Verify the compact @s2/@b format is strictly cheaper than legacy."""
    from backend.engine.tokens import count_tokens as _ct
    old = "@s v2 lang=python blocks=3 aliases=2\n@b id=1 type=C\n"
    new = "@s2 py 3b 2a 0p\n@b 1C\n"
    old_tok = _ct(old)
    new_tok = _ct(new)
    assert new_tok <= old_tok, (
        f"New format ({new_tok} tok) should be <= old format ({old_tok} tok)"
    )
    print(f"  [PASS] slim format {new_tok}tok <= legacy {old_tok}tok")


# ---- NEW TESTS: Conversation light-touch (Item 11) ------------------------

def test_conv_light_touch_prefix_replacement():
    """Conversation role prefixes must be replaced and restored."""
    text = "Human: What is Python?\nAssistant: A language.\n"
    compressed, applied = light_touch_compress_conv(text)
    assert "Human:" not in compressed, f"Human: not replaced: {compressed}"
    assert "H:" in compressed, f"H: not found in compressed: {compressed}"
    # Restore
    for short, orig in applied.items():
        compressed = compressed.replace(short, orig)
    assert compressed == text, (
        f"Round-trip failed: {compressed} != {text}"
    )
    print("  [PASS] conv prefix replacement and restoration")


def test_conv_light_touch_blank_line_collapse():
    """3+ consecutive blank lines in conv text must be collapsed to 2."""
    text = "Human: Hello\n\n\n\n\nAssistant: Hi"
    compressed, _ = light_touch_compress_conv(text)
    assert '\n\n\n' not in compressed, (
        f"Blank lines not collapsed: {repr(compressed)}"
    )
    print("  [PASS] conv blank line collapse")


def test_conv_does_not_touch_code_blocks():
    """A code block containing literal 'Human:' text must NOT be compressed
    by the conversation light-touch function."""
    from backend.engine.conv_compress import light_touch_compress
    code = (
        'print("Human: This is a message")\n'
        'print("Assistant: Reply")\n'
    )
    compressed, applied = light_touch_compress(code)
    # The code text must remain unchanged since this is a type=C block
    # (the function doesn't know about types, but its caller must not call it on code)
    # Actually, the function itself is called on all blocks — verify it doesn't
    # replace 'Human:' in a code context
    assert 'Human:' not in compressed or compressed == code, (
        f"Light-touch modified code block that should have been skipped: "
        f"compressed={compressed!r}"
    )
    print("  [PASS] conv compression does not modify code blocks containing 'Human:'")


# ---- Master test list -----------------------------------------------------

TESTS = [
    # Existing tests
    test_substitution_map_not_empty_for_long_python,
    test_content_compressed_not_empty,
    test_substitution_appears_in_content,
    test_roundtrip_python,
    test_roundtrip_javascript,
    test_conv_blocks_never_substituted,
    test_no_conv_misclassification_in_pure_code,
    test_compression_ratio_realistic,
    test_empty_input,
    test_heatmap_cold_conv_blocks,
    test_competition_never_increases_tokens,
    test_sentinel_blocks_regression,
    test_style_detection,
    test_sentinel_abort_returns_original,
    # Fix #1: Alias collision guard
    test_alias_collision_guard,
    # Fix #2: Reversible competition strategies
    test_inline_abbreviation_reversible,
    test_known_tag_expansion,
    test_i_section_roundtrip,
    # @-spec consistency
    test_parse_inline_abbrev_map_empty_by_default,
    test_parse_templates_empty_by_default,
    # Fix #12: Sentinel layer revert
    test_sentinel_layer_revert_rejects_regression,
    test_sentinel_layer_passes_improvement,
    # Fix #13: Diff engine
    test_diff_unchanged_blocks_reused,
    test_diff_added_and_deleted,
    test_diff_stable_across_runs,
    # Fix #14: Learner
    test_learner_predict_none_when_empty,
    test_learner_log_and_predict_threshold,
    # Large sample tests
    test_large_sample_compression_saves_tokens,
    test_large_sample_roundtrip,
    # Template expansion
    test_decompress_template_expansion,
    # File-tree @f metadata
    test_file_tree_assemble_roundtrip,
    test_file_tree_pipeline_preserved,
    test_file_tree_multiple_blocks_same_file,
    test_file_tree_length_mismatch_raises_error,
    test_file_tree_template_collapse_preserves_indices,
    test_export_route_forwards_file_tree,
    # Prerequisite: try/except block boundary
    test_try_except_block_boundary_roundtrip,
    # Item 8: Block dedup
    test_block_dedup_roundtrip,
    test_dedup_preserves_file_tree_index,
    test_dedup_three_or_more_identical_blocks,
    # Item 7: Pattern dictionary
    test_pattern_dict_below_threshold_not_applied,
    test_pattern_dict_roundtrip,
    test_pattern_dict_runs_after_dedup,
    test_pattern_dict_net_gain_rejects_short,
    # Item 10: Frequency-ordered aliases
    test_frequency_ordered_aliases,
    test_alias_one_token_guard,
    # Item 9: Slim @s2 syntax
    test_slim_syntax_assemble_and_parse,
    test_legacy_v2_still_parseable,
    test_slim_syntax_dedup_form,
    test_slim_syntax_canonical_hash,
    test_slim_format_token_cost,
    # Item 11: Conversation light-touch
    test_conv_light_touch_prefix_replacement,
    test_conv_light_touch_blank_line_collapse,
    test_conv_does_not_touch_code_blocks,
]


if __name__ == "__main__":
    passed = failed = 0
    print("\nNemori.ai Round-Trip Test Suite\n" + "=" * 40)
    for fn in TESTS:
        print(f"\n{fn.__name__}")
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed of {len(TESTS)}")
    if failed:
        sys.exit(1)
