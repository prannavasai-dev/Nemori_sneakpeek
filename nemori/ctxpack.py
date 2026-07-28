"""
ctxpack.py -- Layer 3: Flat @-spec format assembler and parser.

v3 format (current):
  @s3 <lang> <N>b <M>a <K>p [Gg]
  @t K=V K=V ...          -- pre-seeded type aliases
  @u ns1,ns2,ns3           -- collapsed imports
  @n <namespace>           -- namespace header
  @m K=V K=V ...          -- user alias map
  @i K=V K=V ...          -- inline abbreviation map
  @p p<id>=<pattern_text> ... -- pattern dictionary
  @c H:<orig> U:<orig> ...    -- conversation prefix map
  @sig s<id>="signature" ...  -- method signature dedup
  @l l<id>="lambda" ...       -- lambda consolidation
  @i i<id>="idiom" ...        -- idiom dictionary
  @j id:r,c id:r,c ...      -- minor/junction blocks
  @x b1:b3,b7 ...
  @f path0 path1 ...
  @b <id><type> [=dedup_ref] [f=<idx>]
  <content lines>

See assemble() and parse() docstrings for detailed field descriptions.
"""

import re
from urllib.parse import quote, unquote

_TYPE_ENC = {'code': 'C', 'conv': 'V'}
_TYPE_DEC = {'C': 'code', 'V': 'conv'}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assemble(
    blocks: list[dict],
    alias_map: dict[str, str],
    lang: str,
    conn_index: dict[str, list[str]] | None = None,
    alias_freq: dict[str, int] | None = None,
    inline_abbrev_map: dict[str, str] | None = None,
    file_tree: list[str] | None = None,
    pattern_map: dict[str, str] | None = None,
    conv_prefix_map: dict[str, str] | None = None,
    type_alias_map: dict[str, str] | None = None,
    collapsed_imports: list[str] | None = None,
    namespace: str | None = None,
    sig_map: dict[str, str] | None = None,
    lam_map: dict[str, str] | None = None,
    idiom_map: dict[str, str] | None = None,
    **kwargs
) -> str:
    """
    Build the @-spec ctxpack string from pipeline outputs (v3 syntax).

    blocks     -- list of {'type': 'code'|'conv', 'content': str}
                  May include 'dedup_ref' (int) for duplicate blocks.
    alias_map  -- {short_label: original_identifier}
    lang       -- detected language string
    conn_index -- optional {block_id: [connected_block_id, ...]} from grid.py
    alias_freq -- optional {original_identifier: frequency} for sorting @m
    inline_abbrev_map -- optional {original_identifier: abbreviation} for @i
    file_tree  -- optional list of source file paths in order
    pattern_map -- optional {ref_token: pattern_text} for @p section
    conv_prefix_map -- optional {short_prefix: original_prefix} for @c section
    type_alias_map -- optional {alias: original_type} for @t section
    collapsed_imports -- optional list of imported namespaces for @u section
    namespace -- optional namespace string for @n section
    sig_map -- optional {ref: signature} for @sig section (values URL-encoded)
    lam_map -- optional {ref: lambda_expr} for @l section (values URL-encoded)
    idiom_map -- optional {ref: idiom} for @i section (values URL-encoded)
    generic_alias_map -- optional {alias: original_type} for @g section

    Returns a flat text string, never JSON.
    """
    parts: list[str] = []

    # Validate file_tree length against raw input block count (pre-filter)
    if file_tree is not None and len(file_tree) != len(blocks):
        raise ValueError(
            f"file_tree length ({len(file_tree)}) must match block count ({len(blocks)})"
        )

    # Separate template_collapse blocks from regular @b blocks.
    # When file_tree is provided, filter it alongside so surviving
    # blocks keep the correct file path index (Bug 3 fix).
    template_lines: list[str] = []
    regular_blocks: list[dict] = []
    regular_file_tree: list[str] = []
    for i, block in enumerate(blocks):
        if block.get('strategy') == 'template_collapse':
            content = block.get('content', '').rstrip('\n')
            if content:
                template_lines.append(content)
        else:
            regular_blocks.append(block)
            if file_tree is not None:
                regular_file_tree.append(file_tree[i])

    num_aliases = len(alias_map)
    num_patterns = len(pattern_map) if pattern_map else 0
    g_suffix = f" {kwargs.get('grid_size')}g" if kwargs.get('grid_size') else ""

    # @s3 header — always emits all four counts even when zero
    parts.append(
        f'@s3 {lang} {len(regular_blocks)}b {num_aliases}a {num_patterns}p{g_suffix}'
    )

    # @t pre-seeded type aliases (sorted alphabetically by alias)
    if type_alias_map:
        sorted_pairs = sorted(type_alias_map.items(), key=lambda x: x[0])
        parts.append(f'@t {" ".join(f"{k}={v}" for k, v in sorted_pairs)}')

    # @g generic type aliases (sorted alphabetically by alias)
    generic_alias_map = kwargs.get('generic_alias_map')
    if generic_alias_map:
        sorted_pairs = sorted(generic_alias_map.items(), key=lambda x: x[0])
        parts.append(f'@g {" ".join(f"{k}={v}" for k, v in sorted_pairs)}')

    # @u collapsed imports
    if collapsed_imports:
        parts.append(f'@u {",".join(collapsed_imports)}')

    # @n namespace header
    if namespace:
        parts.append(f'@n {namespace}')

    # @m alias line — sorted by frequency (most-used first) when alias_freq provided
    if alias_map:
        if alias_freq:
            sorted_pairs = sorted(
                alias_map.items(),
                key=lambda item: alias_freq.get(item[1], 0),
                reverse=True,
            )
        else:
            sorted_pairs = list(alias_map.items())
        pairs = ' '.join(f'{k}={v}' for k, v in sorted_pairs)
        parts.append(f'@m {pairs}')

    # @i inline abbreviation map (reversible — decompressor expands it)
    if inline_abbrev_map:
        pairs = ' '.join(f'{k}={v}' for k, v in inline_abbrev_map.items())
        parts.append(f'@i {pairs}')

    # @p pattern dictionary — URL-encode values so multi-word patterns
    # survive the space-delimited format
    if pattern_map:
        pairs = ' '.join(f'{k}={quote(v, safe="")}' for k, v in pattern_map.items())
        parts.append(f'@p {pairs}')

    # @c conversation prefix map
    if conv_prefix_map:
        pairs = ' '.join(f'{k}={v}' for k, v in conv_prefix_map.items())
        parts.append(f'@c {pairs}')

    # @sig method signature dedup
    if sig_map:
        pairs = ' '.join(f'{k}={quote(v, safe="")}' for k, v in sig_map.items())
        parts.append(f'@sig {pairs}')

    # @l lambda consolidation
    if lam_map:
        pairs = ' '.join(f'{k}={quote(v, safe="")}' for k, v in lam_map.items())
        parts.append(f'@l {pairs}')

    # @I idiom dictionary (uppercase I to avoid collision with @i inline abbrevs)
    if idiom_map:
        pairs = ' '.join(f'{k}={quote(v, safe="")}' for k, v in idiom_map.items())
        parts.append(f'@I {pairs}')

    # @j minor blocks / junctions (extremely compact: id:r,c)
    minor_patterns = kwargs.get('minor_patterns', [])
    if minor_patterns:
        j_parts = []
        for mb in minor_patterns:
            if mb.get('grid_pos'):
                r, c = mb['grid_pos']
                j_parts.append(f"{mb['id']}:{r},{c}")
        if j_parts:
            parts.append(f"@j {' '.join(j_parts)}")

    # @x connection index (after @m, before @f — omit if empty)
    if conn_index:
        from .grid import format_connection_index
        x_line = format_connection_index(conn_index)
        if x_line:
            parts.append(f'@x {x_line}')

    # @f file tree (after @x, before @t — omit if not provided)
    if regular_file_tree:
        parts.append(f'@f {" ".join(regular_file_tree)}')

    # @t section (template collapse — omit if no template blocks)
    if template_lines:
        parts.append('\n'.join(template_lines))

    # @b blocks with v3 compact syntax
    for i, block in enumerate(regular_blocks, 1):
        btype = _TYPE_ENC.get(block.get('type', 'code'), 'C')
        dedup_ref = block.get('dedup_ref')
        canon_hash = block.get('canonical_hash', '')
        # Compact form: @b <id><type>[=<dedup_ref>] [f=<idx>] [h=<canonical_hash>]
        if dedup_ref is not None:
            b_line = f'@b {i}{btype}={dedup_ref}'
        else:
            b_line = f'@b {i}{btype}'
        if regular_file_tree:
            b_line += f' f={i - 1}'
        if canon_hash:
            b_line += f' h={canon_hash[:16]}'
        gps = block.get('grid_pos')
        if gps and len(gps) >= 2:
            b_line += f' g={gps[0]},{gps[1]}'
        parts.append(b_line)
        if not block.get('dedup_ref'):
            content = block.get('content', '').rstrip('\n')
            parts.append(content)

    return '\n'.join(parts)


def parse(ctxpack_str: str) -> dict:
    """
    Parse a @-spec ctxpack string into a structured dict.

    Supports both v2 (legacy @s2) and v3 (slim @s3) formats.

    Returns:
        {
            'lang':             str,
            'alias_map':        {short: original},
            'inline_abbrev_map': {original: abbreviation},
            'pattern_map':      {ref_token: pattern_text},
            'conv_prefix_map':  {short_prefix: original_prefix},
            'conn_index':       {block_id: [connected_ids]},
            'file_tree':        [str],
            'templates':        [{'template': str, 'arg_list': str}],
            'blocks':           [{'id': int, 'type': 'code'|'conv', 'content': str, 'file_index': int | None, 'dedup_ref': int | None}],
        }
    """
    lang = 'unknown'
    alias_map: dict[str, str] = {}
    inline_abbrev_map: dict[str, str] = {}
    pattern_map: dict[str, str] = {}
    conv_prefix_map: dict[str, str] = {}
    conn_index: dict[str, list[str]] = {}
    file_tree: list[str] = []
    templates: list[dict] = []
    blocks: list[dict] = []
    type_alias_map: dict[str, str] = {}
    collapsed_imports: list[str] = []
    namespace: str = ''
    sig_map: dict[str, str] = {}
    lam_map: dict[str, str] = {}
    idiom_map: dict[str, str] = {}

    current_block: dict | None = None
    content_lines: list[str] = []

    format_version = 2  # default for backward compat
    grid_size = 32

    for raw_line in ctxpack_str.split('\n'):
        line = raw_line.strip()
        if not line and not current_block:
            continue
            
        if line.startswith('@s3 '):
            format_version = 3
            # @s3 <lang> <N>b <M>a <K>p [Gg]
            tokens = raw_line.split()
            if len(tokens) >= 2:
                lang = tokens[1]
            for t in tokens:
                if t.endswith('g'):
                    try:
                        grid_size = int(t[:-1])
                    except ValueError:
                        pass
            # blocks/aliases/patterns counts are informational, stored on blocks list

        elif line.startswith('@s '):
            format_version = 2
            for token in line.split():
                if token.startswith('lang='):
                    lang = token[5:]

        elif line.startswith('@m '):
            for pair in line[3:].split():
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    alias_map[k.strip()] = v.strip()

        elif line.startswith('@i '):
            for pair in line[3:].split():
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    inline_abbrev_map[k.strip()] = v.strip()

        elif line.startswith('@I '):
            for pair in line[3:].split():
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    idiom_map[k.strip()] = unquote(v.strip())

        elif line.startswith('@p '):
            for pair in line[3:].split():
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    pattern_map[k.strip()] = unquote(v.strip())

        elif line.startswith('@c '):
            for pair in line[3:].split():
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    conv_prefix_map[k.strip()] = v.strip()

        elif line.startswith('@sig '):
            for pair in line[5:].split():
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    sig_map[k.strip()] = unquote(v.strip())

        elif line.startswith('@l '):
            for pair in line[3:].split():
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    lam_map[k.strip()] = unquote(v.strip())

        elif line.startswith('@j '):
            for entry in line[3:].split():
                if ':' not in entry:
                    continue
                jid, coords = entry.split(':', 1)
                if ',' in coords:
                    try:
                        r, c = map(int, coords.split(','))
                        # We don't store the full minor block data here, 
                        # just id and pos for occupancy restoration.
                        templates.append({'minor_id': jid, 'grid_pos': [r, c]})
                    except ValueError:
                        pass

        elif line.startswith('@x '):
            for entry in line[3:].split():
                if ':' not in entry:
                    continue
                bid, neighbours = entry.split(':', 1)
                conn_index[bid.strip()] = [n.strip() for n in neighbours.split(',') if n.strip()]

        elif line.startswith('@f '):
            file_tree = line[3:].split()

        elif line.startswith('@u '):
            collapsed_imports = [s.strip() for s in line[3:].split(',') if s.strip()]

        elif line.startswith('@n '):
            namespace = line[3:].strip()

        elif line.startswith('@t '):
            rest = line[3:].strip()
            if '=' in rest:
                for pair in rest.split():
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        type_alias_map[k.strip()] = v.strip()
            else:
                if current_block is not None:
                    current_block['content'] = '\n'.join(content_lines).strip()
                    blocks.append(current_block)
                    content_lines = []
                    current_block = None
                templates.append({'template': rest, 'arg_list': ''})
            continue

        elif line.startswith('@a '):
            # Argument list following a @t — append to the last template
            if templates:
                templates[-1]['arg_list'] = line[3:].strip()
            continue

        elif line.startswith('@b '):
            # Flush previous block
            if current_block is not None:
                current_block['content'] = '\n'.join(content_lines).strip()
                blocks.append(current_block)
                content_lines = []

            block_id: int | None = None
            block_type = 'code'
            file_index: int | None = None
            dedup_ref: int | None = None
            canonical_hash: str = ''
            grid_pos: list[int] = []
            rest = line[3:].strip()

            if format_version == 2:
                # v2: @b id=<n> type=<C|V> [f=<idx>] [=dedup_ref] [h=<hash>]
                for token in rest.split():
                    if token.startswith('id='):
                        try:
                            block_id = int(token[3:])
                        except ValueError:
                            block_id = None
                    elif token.startswith('type='):
                        block_type = _TYPE_DEC.get(token[5:], 'code')
                    elif token.startswith('f='):
                        try:
                            file_index = int(token[2:])
                        except ValueError:
                            file_index = None
                    elif token.startswith('h='):
                        canonical_hash = token[2:]
                    elif token.startswith('g='):
                        try:
                            grid_pos = [int(x) for x in token[2:].split(',')]
                        except ValueError:
                            grid_pos = []
                    elif token.startswith('='):
                        try:
                            dedup_ref = int(token[1:])
                        except ValueError:
                            pass
            else:
                # v3: @b <id><type>[=<dedup_ref>] [f=<idx>] [h=<hash>]
                tokens = rest.split()
                if tokens:
                    first = tokens[0]
                    # Parse '<id><type>' format: e.g. '1C', '2V', '3C=2'
                    eq_pos = first.find('=')
                    if eq_pos != -1:
                        id_type_part = first[:eq_pos]
                        try:
                            dedup_ref = int(first[eq_pos + 1:])
                        except ValueError:
                            dedup_ref = None
                    else:
                        id_type_part = first
                    # Extract type suffix (last char is C or V)
                    if id_type_part and id_type_part[-1] in ('C', 'V'):
                        try:
                            block_id = int(id_type_part[:-1])
                        except ValueError:
                            block_id = None
                        block_type = _TYPE_DEC.get(id_type_part[-1], 'code')
                    else:
                        try:
                            block_id = int(id_type_part)
                        except ValueError:
                            block_id = None
                    # Remaining tokens for optional keys
                    for token in tokens[1:]:
                        if token.startswith('f='):
                            try:
                                file_index = int(token[2:])
                            except ValueError:
                                file_index = None
                        elif token.startswith('h='):
                            canonical_hash = token[2:]
                        elif token.startswith('g='):
                            try:
                                grid_pos = [int(x) for x in token[2:].split(',')]
                            except ValueError:
                                grid_pos = []

            current_block = {
                'id': block_id,
                'type': block_type,
                'file_index': file_index,
                'dedup_ref': dedup_ref,
                'canonical_hash': canonical_hash,
                'grid_pos': grid_pos,
            }

        else:
            # Content line — belongs to the current block
            if current_block is not None:
                content_lines.append(raw_line)

    # Flush the last block
    if current_block is not None:
        current_block['content'] = '\n'.join(content_lines).strip()
        blocks.append(current_block)

    return {
        'lang': lang,
        'alias_map': alias_map,
        'inline_abbrev_map': inline_abbrev_map,
        'pattern_map': pattern_map,
        'conv_prefix_map': conv_prefix_map,
        'type_alias_map': type_alias_map,
        'collapsed_imports': collapsed_imports,
        'namespace': namespace,
        'sig_map': sig_map,
        'lam_map': lam_map,
        'idiom_map': idiom_map,
        'conn_index': conn_index,
        'file_tree': file_tree,
        'templates': [t for t in templates if 'template' in t],
        'minor_patterns': [{'id': t['minor_id'], 'grid_pos': t['grid_pos']} for t in templates if 'minor_id' in t],
        'blocks': blocks,
        'grid_size': grid_size,
    }


def preview(ctxpack_str: str, chars: int = 400) -> str:
    """Return the first N characters of the ctxpack string."""
    if len(ctxpack_str) <= chars:
        return ctxpack_str
    return ctxpack_str[:chars] + '\n...(truncated)'
