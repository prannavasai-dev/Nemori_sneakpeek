"""
decompressor.py  —  Inverse of the compress pipeline.

Given a .ctxpack @-spec flat string, expands every block's content back
to the original identifier names using the alias map, then
reassembles them into a single text string.

Expansion order (important for correctness):
   1. Pattern dictionary refs (@p)       — expand first since patterns may contain
      aliased or abbreviated identifiers that need their own expansion.
   2. Type alias refs (@t)               — expand short type aliases back to original names.
   3. Method signature refs (@sig)       — expand s0/s1/… ref tokens to original signatures.
   4. Lambda refs (@l)                   — expand l0/l1/… ref tokens to original lambdas.
   5. Idiom refs (@i)                    — expand i0/i1/… ref tokens to original idioms.
   6. Conversation prefix refs (@c)      — for type=V blocks only.
   7. Dedup references                   — copy content from referenced block.
   8. [KNOWN:tag] markers                — boilerplate patterns.
   9. Alias substitutions (@m)           — short label → original identifier.
  10. Inline abbreviations (@i)          — short form → original snake_case.
  11. Import collapse reversal (@u)      — replace // @u imports comment with original import lines.
  12. Namespace wrapping (@n)            — wrap code blocks in namespace/package declaration.

Limitations (by design — lossless only where possible):
  • Minification (comment stripping, tab→space, operator spacing) is
    NOT reversed — that information is intentionally discarded.
  • What IS reversed: identifier substitution (A → ConnectionPoolManager),
    inline abbreviation (cp → connection_pool),
    known boilerplate markers ([KNOWN:__main__] → if __name__ ...),
    template collapse expansions, pattern dictionary refs, and dedup refs.
  • Output is therefore "minified-original" — functionally identical code
    but without comments or extra whitespace.
"""

import re
from .ctxpack import parse


# Deterministic reverse table for [KNOWN:tag] boilerplate markers.
KNOWN_EXPANSIONS = {
    "__main__": "if __name__ == '__main__':",
    "shebang": "#!/usr/bin/env python",
    "coding": "# -*- coding: utf-8 -*-",
    "pass": "pass",
    "ellipsis": "...",
}


def decompress(ctxpack_str: str) -> dict:
    """
    Expand a ctxpack @-spec string back toward the original text.

    Returns:
        {
          'blocks':               list of {id, type, label, content_expanded},
          'full_text':            all blocks joined with double-newline,
          'substitutions_applied': number of label→original replacements made,
        }
    """
    parsed = parse(ctxpack_str)
    sub_map: dict[str, str] = parsed.get('alias_map', {})
    inline_abbrev_map: dict[str, str] = parsed.get('inline_abbrev_map', {})
    pattern_map: dict[str, str] = parsed.get('pattern_map', {})
    conv_prefix_map: dict[str, str] = parsed.get('conv_prefix_map', {})
    templates: list[dict] = parsed.get('templates', [])
    blocks_raw: list[dict] = parsed.get('blocks', [])
    type_alias_map: dict[str, str] = parsed.get('type_alias_map', {})
    collapsed_imports: list[str] = parsed.get('collapsed_imports', [])
    namespace: str = parsed.get('namespace', '')
    sig_map: dict[str, str] = parsed.get('sig_map', {})
    lam_map: dict[str, str] = parsed.get('lam_map', {})
    idiom_map: dict[str, str] = parsed.get('idiom_map', {})
    lang: str = parsed.get('lang', '')

    expanded_blocks = []
    total_subs = 0

    # First pass: build a lookup for dedup references (blocks ordered by id)
    block_by_id: dict[int, dict] = {}
    for b in blocks_raw:
        bid = b.get('id')
        if bid is not None:
            block_by_id[bid] = b

    # Pre-compute pattern map as {ref_token: pattern_text} for expansion
    # pattern_map is already in that format from parse()
    # @p stores p1=text, etc. — ref_token = §p1 or @@1@@ depending on marker

    for b in blocks_raw:
        compressed = b.get('content', '')

        # Step 1: Expand pattern dictionary refs (@p) — do this FIRST so patterns
        # can themselves contain alias-substituted identifiers
        if pattern_map:
            compressed = _expand_pattern_refs(compressed, pattern_map)

        if b.get('type') == 'code':
            # Step 2: Expand type alias refs (@t) — short aliases back to original type names
            if type_alias_map:
                compressed, n_t = _expand_substitutions(compressed, type_alias_map)
                total_subs += n_t

            # Step 3: Expand method signature refs (@sig)
            for ref_token, original_sig in sig_map.items():
                compressed = compressed.replace(ref_token, original_sig)
                total_subs += 1

            # Step 4: Expand lambda refs (@l)
            for ref_token, original_lam in lam_map.items():
                compressed = compressed.replace(ref_token, original_lam)
                total_subs += 1

            # Step 5: Expand idiom refs (@i)
            for ref_token, original_idiom in idiom_map.items():
                compressed = compressed.replace(ref_token, original_idiom)
                total_subs += 1

        # Step 6: Expand conversation prefix refs (@c) — for conv blocks only
        if b.get('type') == 'conv' and conv_prefix_map:
            # conv_prefix_map stores short → original, expand both directions
            compressed = _expand_conv_prefixes(compressed, conv_prefix_map)

        # Step 7: Handle dedup references — copy content from referenced block
        dedup_ref = b.get('dedup_ref')
        if dedup_ref is not None and dedup_ref in block_by_id:
            ref_block = block_by_id[dedup_ref]
            compressed = ref_block.get('content', '')

        # Step 8: Expand [KNOWN:tag] markers (applies to all block types)
        compressed = _expand_known_markers(compressed)
        known_subs = len(re.findall(r'\[KNOWN:\w+\]', b.get('content', ''))) - \
                     len(re.findall(r'\[KNOWN:\w+\]', compressed))
        total_subs += known_subs

        if b.get('type') == 'code':
            # Step 9: Expand alias substitutions (@m)
            expanded, n = _expand_substitutions(compressed, sub_map)
            total_subs += n

            # Step 10: Expand inline abbreviations (@i)
            # @i stores original→abbrev, so invert to short→original for _expand_substitutions
            reversed_abbrev = {v: k for k, v in inline_abbrev_map.items()}
            expanded, n2 = _expand_substitutions(expanded, reversed_abbrev)
            total_subs += n2
        else:
            expanded = compressed

        expanded_blocks.append({
            'id':               b.get('id', ''),
            'type':             b.get('type', ''),
            'label':            '',
            'content_expanded': expanded,
            'subs_in_block':    total_subs,
        })

    # Post-process: Expand template collapses if present
    if templates:
        expanded_blocks = _expand_templates(templates, expanded_blocks)

    full_text = '\n\n'.join(
        b['content_expanded'] for b in expanded_blocks if b['content_expanded']
    )

    # Step 11: Reverse @u import collapse — prepend original import lines
    if collapsed_imports:
        lang_lower = lang.lower()
        if lang_lower in ('java',):
            prefix, suffix = 'import', ';'
        elif lang_lower in ('csharp',):
            prefix, suffix = 'using', ';'
        elif lang_lower in ('python',):
            prefix, suffix = 'import', ''
        else:
            prefix, suffix = 'import', ''
        import_lines = []
        for imp in collapsed_imports:
            if suffix:
                import_lines.append(f'{prefix} {imp}{suffix}')
            else:
                import_lines.append(f'{prefix} {imp}')
        if import_lines:
            full_text = '\n'.join(import_lines) + '\n\n' + full_text

    # Step 12: Reverse @n namespace — wrap code in namespace/package declaration
    if namespace:
        if lang in ('java', 'Java'):
            full_text = f'package {namespace};\n\n{full_text}'
        else:
            full_text = f'namespace {namespace} {{\n\n{full_text}\n}}'

    return {
        'blocks':                expanded_blocks,
        'full_text':             full_text,
        'substitutions_applied': total_subs,
    }


def _expand_known_markers(text: str) -> str:
    """Reverse [KNOWN:tag] markers back to their original boilerplate patterns."""
    for tag, pattern in KNOWN_EXPANSIONS.items():
        text = text.replace(f'[KNOWN:{tag}]', pattern)
    return text


def _expand_templates(templates: list[dict], blocks: list[dict]) -> list[dict]:
    """
    Expand @t/@a template collapses back into individual function blocks.

    Handles two cases:
      1. Standalone @t/@a sections (parsed into templates list) — generate
         new function blocks for each entry in the arg list.
      2. Block content that starts with @t (old format, kept for compat).
    """
    if not templates:
        return blocks

    expanded: list[dict] = []

    # Case 1: standalone templates from @t/@a sections
    for tpl in templates:
        template_text = tpl.get('template', '')
        arg_list_text = tpl.get('arg_list', '')
        if not template_text or not arg_list_text:
            continue
        entries = arg_list_text.split(';')
        for idx, entry in enumerate(entries):
            if ':' not in entry:
                continue
            func_name, vars_str = entry.split(':', 1)
            var_names = [v.strip() for v in vars_str.split(',') if v.strip()]
            func_body = template_text
            func_body = func_body.replace('FUNC', func_name)
            for i, vname in enumerate(var_names, 1):
                func_body = func_body.replace(f'V{i}', vname)
                func_body = func_body.replace(f'A{i}', vname)
                func_body = func_body.replace(f'ATTR{i}', vname)
            expanded.append({
                'id': f"t{idx + 1}",
                'type': 'code',
                'label': '',
                'content_expanded': func_body,
                'subs_in_block': 0,
            })

    # Case 2: regular blocks (pass through, plus expand any %t block content)
    for b in blocks:
        content = b.get('content_expanded', b.get('content', ''))
        btype = b.get('type', 'code')
        if btype == 'code' and content.startswith('@t ') and templates:
            for tpl in templates:
                template_text = tpl.get('template', '')
                arg_list_text = tpl.get('arg_list', '')
                if not template_text or not arg_list_text:
                    continue
                entries = arg_list_text.split(';')
                for idx, entry in enumerate(entries):
                    if ':' not in entry:
                        continue
                    func_name, vars_str = entry.split(':', 1)
                    var_names = [v.strip() for v in vars_str.split(',') if v.strip()]
                    func_body = template_text
                    func_body = func_body.replace('FUNC', func_name)
                    for i, vname in enumerate(var_names, 1):
                        func_body = func_body.replace(f'V{i}', vname)
                        func_body = func_body.replace(f'A{i}', vname)
                        func_body = func_body.replace(f'ATTR{i}', vname)
                    expanded.append({
                        'id': f"{b.get('id', '')}_{idx + 1}",
                        'type': btype,
                        'label': '',
                        'content_expanded': func_body,
                        'subs_in_block': 0,
                    })
        else:
            expanded.append(b)
    return expanded


def _expand_substitutions(code: str, sub_map: dict[str, str]) -> tuple[str, int]:
    """
    Replace every short label with its original identifier.
    sub_map format: {short: original}  e.g. {'A': 'ConnectionPoolManager'}

    Applies whole-word replacement, longest labels first to avoid
    partial-match issues (e.g. 'AA' before 'A').
    Returns (expanded_code, number_of_replacements_made).
    """
    total = 0
    # Sort by label length descending (AA before A)
    sorted_labels = sorted(sub_map.keys(), key=len, reverse=True)

    for short in sorted_labels:
        original = sub_map[short]
        pattern  = r'\b' + re.escape(short) + r'\b'
        new_code, count = re.subn(pattern, original, code)
        code     = new_code
        total   += count

    return code, total


def verify_round_trip(original_text: str, ctxpack_str: str) -> dict:
    """
    Compress → decompress, then check fidelity.

    Because minification is lossy (strips comments, tabs whitespace),
    we normalise BOTH sides before comparing:
      - collapse all whitespace runs to single space
      - strip blank lines
      - lowercase (identifiers are case-sensitive but punctuation/keywords aren't)

    Returns:
        {
          'match':        bool — True if normalised texts are identical,
          'original_norm': str,
          'recovered_norm': str,
          'diff_chars':   int — character distance between normalised texts,
        }
    """
    result      = decompress(ctxpack_str)
    recovered   = result['full_text']

    orig_norm  = _normalise(original_text)
    recov_norm = _normalise(recovered)

    match = (orig_norm == recov_norm)

    # Find the first differing character position for actionable diagnostics.
    # abs(len diff) alone is useless — equal-length but different strings show diff=0.
    diff_at = -1
    if not match:
        for i, (a, b) in enumerate(zip(orig_norm, recov_norm)):
            if a != b:
                diff_at = i
                break
        if diff_at == -1:   # one is a prefix of the other
            diff_at = min(len(orig_norm), len(recov_norm))

    return {
        'match':         match,
        'original_norm': orig_norm,
        'recovered_norm': recov_norm,
        'diff_chars':    abs(len(orig_norm) - len(recov_norm)),
        'diff_at':       diff_at,   # char index of first mismatch, -1 if match
    }


def _expand_pattern_refs(text: str, pattern_map: dict[str, str]) -> str:
    """
    Expand pattern dictionary references. pattern_map maps ref_token → pattern_text.
    e.g. {'§p1': 'connection_pool_manager'} expands §p1 back to the full pattern.
    """
    for ref_token, pattern_text in pattern_map.items():
        text = text.replace(ref_token, pattern_text)
    return text


def _expand_conv_prefixes(text: str, prefix_map: dict[str, str]) -> str:
    """
    Expand conversation prefix abbreviations. prefix_map maps short → original.
    e.g. {'H:': 'Human:'} expands H: back to Human:.
    """
    for short, original in prefix_map.items():
        text = text.replace(short, original)
    return text


def _normalise(text: str) -> str:
    """
    Normalise two texts so they can be compared after round-trip.

    The minifier strips comments, operator spacing, and collapses whitespace.
    We apply the same reductions to BOTH original and recovered before comparing,
    so intentional losses don't count as mismatches.

    Steps:
      1. Strip C-style block comments (/* ... */) — minifier removes these too
      2. Strip single-line comments (# and //)
      3. Strip spaces around operators (mirrors _strip_operator_spaces)
      4. Collapse ALL remaining whitespace to a single space
    """
    text = re.sub(r'/\*[\s\S]*?\*/', '', text)  # C / JS /* */ block comments
    text = re.sub(r'#[^\n]*', '', text)          # Python / bash # comments
    text = re.sub(r'//[^\n]*', '', text)         # JS / C++ // comments
    text = re.sub(r' *([=+\-*/><!\&|,]) *', r'\1', text)  # operator spacing
    text = re.sub(r'\s+', ' ', text)             # collapse all whitespace
    return text.strip()
