"""
competition.py — Layer 2: Token Competition Engine

For every hot block from heatmap.py, 5 strategies compete.
tiktoken cl100k_base judges every strategy.
Winner = lowest total token cost. Always.
"""

from __future__ import annotations

import ast
import re
from typing import Any

from .minifier import _enc, PROTECTED_KEYWORDS
from .substitution import build_substitution_map, apply_substitutions
from .heatmap import HeatResult


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KNOWN_PATTERNS = {
    "if __name__ == '__main__':": "__main__",
    "#!/usr/bin/env python": "shebang",
    "# -*- coding: utf-8 -*-": "coding",
    "pass": "pass",
    "...": "ellipsis",
}


# ---------------------------------------------------------------------------
# Token helper
# ---------------------------------------------------------------------------

def _tok(text: str) -> int:
    """Exact token count via tiktoken cl100k_base, fallback to heuristic."""
    if _enc is not None:
        return len(_enc.encode(text))
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------

def _strategy_keep_original(content: str) -> tuple[int, str, dict]:
    """Baseline: untouched content."""
    return _tok(content), content, {}


def _strategy_alias_substitution(content: str, num_blocks: int = 1) -> tuple[int, str, dict]:
    """
    Evaluate the token cost of alias substitution WITHOUT embedding an @m header
    inside the block content.  The global sub_map in compress.py is built
    separately and applied uniformly — we must NOT format the block here.

    Returns a cost estimate that includes the amortized @m header overhead so
    that the tournament comparison is fair, but the returned content is just the
    substituted text (no @m line) so it can be fed into the assembler cleanly.

    The @m header appears once globally in the ctxpack, not per-block.
    num_blocks amortizes this cost so multi-block inputs don't overpenalize
    the alias strategy.
    """
    sub_map = build_substitution_map(content)
    if not sub_map:
        return float('inf'), content, {}

    substituted = apply_substitutions(content, sub_map)
    # Estimate header overhead (will appear once in @m, not per-block)
    header_cost = _tok('@m ' + ' '.join(f'{k}={v}' for k, v in sub_map.items()))
    amortized_header = max(1, header_cost // num_blocks)
    total_cost = _tok(substituted) + amortized_header
    return total_cost, substituted, {}


def _strategy_template_collapse(content: str) -> tuple[int, str, dict]:
    """
    Detect 3+ functions with identical AST structure (different names).
    Returns a @template / @args representation.
    Auto-loses if fewer than 3 identical structures.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return float('inf'), content, {}

    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(funcs) < 3:
        return float('inf'), content, {}

    groups: dict[str, list[ast.FunctionDef]] = {}
    for func in funcs:
        sig = _structural_hash(func)
        groups.setdefault(sig, []).append(func)

    for sig, group in groups.items():
        if len(group) >= 3:
            template = _build_template(group[0])
            arg_list = _build_arg_list(group)
            result = f'@t {template}\n@a {arg_list}\n'
            metadata = {'template': template, 'arg_list': arg_list}
            return _tok(result), result, metadata

    return float('inf'), content, {}


def _strategy_inline_abbreviation(content: str) -> tuple[int, str, dict]:
    """
    snake_case identifiers → first-letter abbreviations.
    Returns metadata with the abbreviation map for decompression.
    """
    abbreviated, abbrev_map = _inline_abbreviate(content)
    return _tok(abbreviated), abbreviated, {'abbrev_map': abbrev_map}


def _strategy_drop_boilerplate(content: str) -> tuple[int, str, dict]:
    """
    Replace known boilerplate patterns with [KNOWN:tag] markers.
    Tags are deterministic — the reverse table in decompressor.py
    can expand them without a per-output map.
    """
    result, applied_tags = _drop_boilerplate(content)
    return _tok(result), result, {'known_tags': applied_tags}


# ---------------------------------------------------------------------------
# Template-collapse helpers
# ---------------------------------------------------------------------------

def _structural_hash(node: ast.AST) -> str:
    """
    Hash of AST structure ignoring all identifier names.
    Two functions with identical structure but different variable names
    will produce the same hash.
    """
    parts: list[str] = []

    def visit(n: ast.AST) -> None:
        parts.append(type(n).__name__)
        for field, value in ast.iter_fields(n):
            if field in ('id', 'arg', 'name', 'attr'):
                parts.append('_')
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        visit(item)
            elif isinstance(value, ast.AST):
                visit(value)
            else:
                parts.append(str(value))
        parts.append('/')

    visit(node)
    return ''.join(parts)


def _build_template(func: ast.FunctionDef) -> str:
    """
    Create a generic template from a representative function.
    All identifiers are replaced with generic placeholders.
    """
    try:
        source = ast.unparse(func)
        tree = ast.parse(source)
        func_node = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))][0]

        class Genericizer(ast.NodeTransformer):
            _counter = 0
            def visit_Name(self, node: ast.Name) -> ast.Name:
                self._counter += 1
                return ast.Name(id=f'V{self._counter}', ctx=node.ctx)
            def visit_arg(self, node: ast.arg) -> ast.arg:
                self._counter += 1
                return ast.arg(arg=f'A{self._counter}', annotation=node.annotation, type_comment=node.type_comment)
            def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
                node.name = 'FUNC'
                return self.generic_visit(node)
            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
                node.name = 'FUNC'
                return self.generic_visit(node)
            def visit_Attribute(self, node: ast.Attribute) -> ast.Attribute:
                self._counter += 1
                node.attr = f'ATTR{self._counter}'
                return self.generic_visit(node)

        genericizer = Genericizer()
        genericizer.visit(func_node)
        ast.fix_missing_locations(func_node)
        return ast.unparse(func_node)
    except Exception:
        return 'def FUNC(...): ...'


def _collect_names_dfs(node: ast.AST) -> list[str]:
    """Collect Name nodes in the same depth-first field-order as Genericizer.
    ast.walk uses BFS which produces a different ordering, causing V1/V2/etc.
    placeholders to map to the wrong variables during template expansion.
    """
    names: list[str] = []
    if isinstance(node, ast.Name):
        names.append(node.id)
    for _field, value in ast.iter_fields(node):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, ast.AST):
                    names.extend(_collect_names_dfs(item))
        elif isinstance(value, ast.AST):
            names.extend(_collect_names_dfs(value))
    return names


def _build_arg_list(group: list[ast.FunctionDef]) -> str:
    """Compact argument list mapping each function to its identifier names."""
    parts = []
    for func in group:
        names = _collect_names_dfs(func)
        parts.append(f'{func.name}:{",".join(names)}')
    return ';'.join(parts)


def _split_string_regions(code: str) -> list[tuple[bool, str]]:
    """
    Split code into [(is_string, text), ...] segments.
    is_string=True means this segment is inside a string literal.
    Handles single-quoted, double-quoted, triple-quoted, and backtick strings.
    """
    segments: list[tuple[bool, str]] = []
    i = 0
    while i < len(code):
        # Check for triple-quoted strings first
        if code[i:i+3] in ('"""', "'''"):
            quote = code[i:i+3]
            end = code.find(quote, i + 3)
            if end == -1:
                end = len(code)
            else:
                end += 3
            segments.append((True, code[i:end]))
            i = end
            continue
        # Check for backtick strings (JS template literals)
        if code[i] == '`':
            end = code.find('`', i + 1)
            if end == -1:
                end = len(code) + 1
            else:
                end += 1
            segments.append((True, code[i:end]))
            i = end
            continue
        # Check for single/double quoted strings
        if code[i] in ('"', "'"):
            quote = code[i]
            j = i + 1
            while j < len(code):
                if code[j] == '\\':
                    j += 2
                    continue
                if code[j] == quote:
                    j += 1
                    break
                j += 1
            segments.append((True, code[i:j]))
            i = j
            continue
        # Not a string literal — collect non-string text
        j = i
        while j < len(code) and code[j] not in ('"', "'", '`'):
            if j + 2 < len(code) and code[j:j+3] in ('"""', "'''"):
                break
            j += 1
        segments.append((False, code[i:j]))
        i = j
    return segments


def _inline_abbreviate(content: str) -> tuple[str, dict]:
    """
    Replace snake_case identifiers with first-letter abbreviations.
    e.g. connection_pool → cp

    Returns (abbreviated_content, abbrev_map) where abbrev_map maps
    original_identifier → abbreviated_form for use in the @i section.

    Collision guard: if two identifiers produce the same abbreviation
    (e.g. connection_pool and cache_pool both → cp), we skip both rather
    than silently mapping them to the same alias. Also skips abbreviations
    that collide with existing identifiers in the code.

    String literals are protected from abbreviation.
    """
    # First, collect all identifiers from non-string regions
    segments = _split_string_regions(content)
    idents = set()
    for is_string, text in segments:
        if not is_string:
            idents.update(re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', text))
    
    abbrev_map: dict[str, str] = {}
    used_abbrevs: set[str] = set()
    # Collision guard: any existing identifier that is a single short word
    # (e.g. "cp" already exists as a variable) must not be used as an abbrev
    existing_in_code = {i.lower() for i in idents}
    for ident in sorted(idents, key=len, reverse=True):  # longest first = most savings
        if ident in PROTECTED_KEYWORDS:
            continue
        if '_' not in ident:
            continue
        parts = ident.split('_')
        abbrev = ''.join(p[0] for p in parts if p)
        if abbrev and len(abbrev) < len(ident) and abbrev not in used_abbrevs:
            if abbrev.lower() not in existing_in_code:
                abbrev_map[ident] = abbrev
                used_abbrevs.add(abbrev)
        # else: skip — collision or no saving
    
    # Apply abbreviations only to non-string regions
    result_parts = []
    for is_string, text in segments:
        if is_string:
            result_parts.append(text)
        else:
            for ident in sorted(abbrev_map.keys(), key=len, reverse=True):
                text = re.sub(r'\b' + re.escape(ident) + r'\b', abbrev_map[ident], text)
            result_parts.append(text)
    return ''.join(result_parts), abbrev_map


def _drop_boilerplate(content: str) -> tuple[str, list[str]]:
    """Replace known boilerplate patterns with compact [KNOWN:tag] markers.
    Returns (content, list_of_applied_tags)."""
    applied = []
    for pattern, tag in KNOWN_PATTERNS.items():
        if pattern in content:
            content = content.replace(pattern, f'[KNOWN:{tag}]')
            applied.append(tag)
    return content, applied


def compete_block(content: str, lang: str, predicted_strategy: str | None = None, num_blocks: int = 1) -> dict[str, Any]:
    """
    Run the 5-strategy competition on a single block.

    When predicted_strategy is provided (from Layer 7 learner), the
    tournament is short-circuited: only that single strategy runs.
    The sentinel layer gate still guards against regression.

    num_blocks amortizes the per-block @m header cost so multi-block
    inputs don't overpenalize the alias substitution strategy.

    Returns:
        {
            'content':            str,
            'strategy':           str,
            'strategy_metadata':  dict,
            'tokens_before':      int,
            'tokens_after':       int,
            'tokens_saved':       int,
        }
    """
    tokens_before = _tok(content)

    strategies = {
        'keep_original':       _strategy_keep_original(content),
        'alias_substitution':  _strategy_alias_substitution(content, num_blocks),
        'template_collapse':   _strategy_template_collapse(content),
        'inline_abbreviation': _strategy_inline_abbreviation(content),
        'drop_boilerplate':    _strategy_drop_boilerplate(content),
    }

    if predicted_strategy and predicted_strategy in strategies:
        # Short-circuit: run only the predicted strategy, sentinel-guarded
        pred_cost, pred_content, pred_metadata = strategies[predicted_strategy]
        if pred_cost < tokens_before:
            return {
                'content':            pred_content,
                'strategy':           predicted_strategy,
                'strategy_metadata':  pred_metadata,
                'tokens_before':      tokens_before,
                'tokens_after':       pred_cost,
                'tokens_saved':       max(0, tokens_before - pred_cost),
            }
        # Regression: fall through to full tournament

    winner_name = min(strategies, key=lambda k: strategies[k][0])
    winner_cost, winner_content, winner_metadata = strategies[winner_name]

    if winner_cost >= tokens_before:
        winner_name = 'keep_original'
        winner_content = content
        winner_cost = tokens_before
        winner_metadata = {}

    return {
        'content':            winner_content,
        'strategy':           winner_name,
        'strategy_metadata':  winner_metadata,
        'tokens_before':      tokens_before,
        'tokens_after':       winner_cost,
        'tokens_saved':       max(0, tokens_before - winner_cost),
    }


def compete_blocks(chunks: list[dict], lang: str, predicted_strategy: str | None = None) -> list[dict]:
    """
    Run competition on a list of chunk dicts from heatmap.scan_blocks.
    Cold blocks and conv blocks skip competition entirely.

    predicted_strategy is an optional Layer 7 hint that short-circuits
    the per-block tournament when the learner has high confidence.

    num_code_blocks is counted to amortize the @m header cost across
    all code blocks (the header appears once globally in ctxpack).
    """
    num_code_blocks = sum(1 for c in chunks if c.get('type') == 'code')
    result = []
    for chunk in chunks:
        heat: HeatResult | None = chunk.get('heat')
        is_hot = heat.is_hot if heat is not None else False

        if chunk.get('type') == 'conv' or not is_hot:
            result.append({
                **chunk,
                'strategy':           'keep_original',
                'strategy_metadata':  {},
                'tokens_before':      _tok(chunk.get('content', '')),
                'tokens_after':       _tok(chunk.get('content', '')),
                'tokens_saved':       0,
            })
            continue

        competition_result = compete_block(chunk['content'], lang, predicted_strategy, num_code_blocks)
        result.append({
            **chunk,
            **competition_result,
        })

    return result
