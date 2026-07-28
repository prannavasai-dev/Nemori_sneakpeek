"""
analyzer.py
Detects whether a chunk of text is code or conversation.
Uses a scoring approach — not a single regex, but a weighted vote.

FIX: _split_by_turns was misclassifying pure-code chunks as 'conv'.
     Now: if a function-split block's first line matches a code definition
     keyword, it is forced to 'code' regardless of score_chunk().
     Also raised the conv-signal threshold so stray question marks in
     comments don't tip the balance.
"""

import os
import re

# ─── Pygments-based language detection ──────────────────────────────────────
try:
    from pygments.lexers import guess_lexer, guess_lexer_for_filename, get_lexer_by_name
    from pygments.util import ClassNotFound
    PYGMENTS_AVAILABLE = True
except Exception:
    PYGMENTS_AVAILABLE = False

# Map Pygments lexer aliases to our internal language identifiers
_PYGMENTS_TO_INTERNAL = {
    'python': 'python',
    'python3': 'python',
    'py': 'python',
    'csharp': 'csharp',
    'cs': 'csharp',
    'c#': 'csharp',
    'java': 'java',
    'cpp': 'cpp',
    'c++': 'cpp',
    'c': 'c',
    'javascript': 'javascript',
    'js': 'javascript',
    'typescript': 'typescript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'jsx': 'javascript',
    'go': 'go',
    'golang': 'go',
    'rust': 'rust',
    'rs': 'rust',
    'kotlin': 'kotlin',
    'kt': 'kotlin',
    'kts': 'kotlin',
    'sql': 'sql',
    'mysql': 'sql',
    'postgresql': 'sql',
    'sqlite': 'sql',
    'php': 'php',
    'ruby': 'ruby',
    'rb': 'ruby',
    'swift': 'swift',
    'shell': 'bash',
    'bash': 'bash',
    'sh': 'bash',
    'zsh': 'bash',
    'r': 'r',
    'scala': 'scala',
    'perl': 'perl',
    'pl': 'perl',
    'lua': 'lua',
    'dart': 'dart',
    'elixir': 'elixir',
    'ex': 'elixir',
    'erlang': 'erlang',
    'erl': 'erlang',
    'haskell': 'haskell',
    'hs': 'haskell',
    'clojure': 'clojure',
    'clj': 'clojure',
    'fsharp': 'fsharp',
    'fs': 'fsharp',
    'vb.net': 'vbnet',
    'vb': 'vbnet',
    'objectivec': 'objectivec',
    'obj-c': 'objectivec',
    'objective-c': 'objectivec',
    'groovy': 'groovy',
    'scala': 'scala',
    'r': 'r',
    'matlab': 'matlab',
    'julia': 'julia',
    'jl': 'julia',
    'vue': 'vue',
    'svelte': 'svelte',
}

# Extensions map for Phase 1 (filename-based detection)
_EXT_MAP = {
    '.py': 'python', '.pyw': 'python', '.pyi': 'python',
    '.cs': 'csharp', '.csx': 'csharp',
    '.java': 'java',
    '.cpp': 'cpp', '.hpp': 'cpp', '.h': 'cpp', '.hxx': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.c': 'c',
    '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
    '.ts': 'typescript', '.tsx': 'typescript', '.mts': 'typescript', '.cts': 'typescript',
    '.go': 'go',
    '.rs': 'rust',
    '.kt': 'kotlin', '.kts': 'kotlin',
    '.sql': 'sql',
    '.php': 'php', '.phtml': 'php',
    '.rb': 'ruby', '.rbw': 'ruby', '.rake': 'ruby', '.gemspec': 'ruby',
    '.swift': 'swift',
    '.sh': 'bash', '.bash': 'bash', '.zsh': 'bash', '.fish': 'bash',
    '.r': 'r', '.R': 'r',
    '.scala': 'scala', '.sc': 'scala',
    '.pl': 'perl', '.pm': 'perl', '.t': 'perl',
    '.lua': 'lua',
    '.dart': 'dart',
    '.ex': 'elixir', '.exs': 'elixir',
    '.erl': 'erlang', '.hrl': 'erlang',
    '.hs': 'haskell', '.lhs': 'haskell',
    '.clj': 'clojure', '.cljs': 'clojure', '.cljc': 'clojure', '.edn': 'clojure',
    '.fs': 'fsharp', '.fsx': 'fsharp', '.fsi': 'fsharp',
    '.vb': 'vbnet', '.vbs': 'vbnet',
    '.m': 'objectivec', '.mm': 'objectivec',
    '.groovy': 'groovy', '.gvy': 'groovy', '.gy': 'groovy',
    '.jl': 'julia',
    '.vue': 'vue',
    '.svelte': 'svelte',
}

# Shebang patterns for Phase 1
_SHEBANG_MAP = {
    'python': 'python', 'python3': 'python',
    'node': 'javascript', 'nodejs': 'javascript', 'bun': 'javascript', 'deno': 'javascript',
    'bash': 'bash', 'sh': 'bash', 'zsh': 'bash', 'fish': 'bash',
    'ruby': 'ruby', 'perl': 'perl', 'lua': 'lua',
}

# Keywords that appear in code but almost never in natural conversation
CODE_SIGNALS = [
    (r'^\s*(def |class |async def )', 4),
    (r'^\s*(function |const |let |var |import |from |export )', 4),
    (r'^\s*(public |private |protected |static |void |int |str |bool )', 3),
    (r'^\s*(#include|#define|namespace |using )', 3),
    (r'[;{}]\s*$', 2),                         # line ends with ; { }
    (r'=>\s', 2),                               # arrow function
    (r'\breturn\b', 2),
    (r'\bself\b', 2),
    (r'\bthis\b', 1),
    (r'^\s*(if|for|while|switch)\s*[\(\:]', 2),
    (r'//.*$', 1),                             # single-line comment
    (r'/\*[\s\S]*?\*/', 1),                    # block comment
    (r'^\s*#\s*\w', 1),                        # python comment / pragma
    (r'\.append\(|\.push\(|\.pop\(', 1),
    (r'^\s*@\w+', 1),                          # decorator
    (r'\[.*\]\s*[:=]', 1),                     # list/dict literal
]

# Signals that it's a conversation, not code
# Require a high score to override code signals
CONV_SIGNALS = [
    (r'^(human|assistant|user|claude|gpt|system|me|you)\s*:', 5),
    (r'^\*\*?(human|assistant|user)\*\*?\s*:', 5),
    (r'^>\s+\w', 2),                           # markdown quote
    (r'\?\s*$', 1),                            # ends with question mark
]

# First lines that definitively mean "this block is code"
_CODE_FIRST_LINE = re.compile(
    r'^(def |async def |class |function |const \w|let \w|var \w|'
    r'public |private |protected |static |#include|#pragma|import |from )',
)


def score_chunk(text: str) -> tuple[str, float]:
    """
    Returns ('code' | 'conv', confidence 0.0-1.0).
    """
    lines = text.split('\n')
    non_empty = [l for l in lines if l.strip()]
    if not non_empty:
        return 'conv', 0.5

    code_score = 0
    conv_score = 0

    for line in non_empty:
        for pattern, weight in CODE_SIGNALS:
            if re.search(pattern, line):
                code_score += weight
                break  # only count one signal per line
        for pattern, weight in CONV_SIGNALS:
            if re.search(pattern, line, re.IGNORECASE):
                conv_score += weight
                break

    total = code_score + conv_score
    if total == 0:
        return 'conv', 0.5

    if code_score > conv_score:
        return 'code', round(code_score / total, 2)
    else:
        return 'conv', round(conv_score / total, 2)


def detect_language(text: str, filename: str = '') -> str:
    """
    Detect programming language using Pygments (primary) with filename/shebang fallback.

    Phase 1 — Extension/Shebang (if available):
      Uses filename extension or shebang line for fast, accurate detection.

    Phase 2 — Pygments lexical analysis:
      Uses Pygments' guess_lexer/guess_lexer_for_filename which implements
      sophisticated lexer-specific analyse_text() heuristics.

    Phase 3 — Smart fallback:
      If Pygments returns a low-confidence result (e.g., generic "Python" for
      non-Python code), falls back to robust keyword-based heuristic.

    Returns internal language identifier: python, csharp, java, cpp, javascript,
    typescript, go, rust, kotlin, sql, etc.
    """
    # ── Phase 1: Extension / Shebang ──────────────────────────────────────────
    if filename:
        _, ext = os.path.splitext(filename)
        ext_lower = ext.lower()
        if ext_lower in _EXT_MAP:
            return _EXT_MAP[ext_lower]

    first_line = text.split('\n', 1)[0].strip()
    if first_line.startswith('#!'):
        shebang = first_line[2:].strip().lower()
        for key, lang in _SHEBANG_MAP.items():
            if key in shebang:
                return lang

    # ── Phase 2: Pygments lexical analysis ────────────────────────────────────
    pygments_lang = None
    if PYGMENTS_AVAILABLE and text.strip():
        try:
            if filename:
                lexer = guess_lexer_for_filename(filename, text)
            else:
                lexer = guess_lexer(text)

            # Map Pygments lexer alias to our internal identifier
            for alias in lexer.aliases:
                if alias in _PYGMENTS_TO_INTERNAL:
                    pygments_lang = _PYGMENTS_TO_INTERNAL[alias]
                    break

            # Fallback: try the primary name
            if pygments_lang is None:
                name_lower = lexer.name.lower()
                if name_lower in _PYGMENTS_TO_INTERNAL:
                    pygments_lang = _PYGMENTS_TO_INTERNAL[name_lower]

        except ClassNotFound:
            pass  # Fall through to fallback

    # ── Phase 3: Smart fallback ───────────────────────────────────────────────
    # If Pygments detected a language confidently (not generic Python for non-Python
    # code), use it. Otherwise fall back to keyword heuristic.
    fallback_lang = _detect_language_fallback(text)

    if pygments_lang and pygments_lang != 'python':
        # Pygments confidently detected a non-Python language
        return pygments_lang

    if pygments_lang == 'python':
        # Pygments says Python — check if fallback agrees or strongly disagrees
        if fallback_lang == 'python':
            return 'python'
        # Fallback strongly suggests another language; trust fallback for known patterns
        # Check if fallback has high-confidence markers for its language
        if _has_strong_language_markers(text, fallback_lang):
            return fallback_lang
        # Otherwise, Pygments' Python might be right (e.g., actual Python code)
        return 'python'

    # Pygments failed or returned unknown — use fallback
    return fallback_lang


def _detect_language_fallback(text: str) -> str:
    """
    Original keyword-based language detection as fallback.
    """
    sample_lines = text.split('\n')[:50]
    sample = '\n'.join(sample_lines)

    score: dict[str, float] = {}

    # Python
    py = 0.0
    # Python: def/class, import without braces/quotes, from X import Y (no quotes around X)
    if re.search(r'^\s*(def |async def |class .+:)', sample, re.MULTILINE):
        py += 3.0
    # Python-specific import patterns (no quotes, no braces)
    if re.search(r'^\s*import\s+[\w.]+(\s+as\s+\w+)?(\s*,\s*[\w.]+(\s+as\s+\w+)?)*\s*$', sample, re.MULTILINE):
        py += 2.0
    if re.search(r'^\s*from\s+[\w.]+\s+import\s+', sample, re.MULTILINE):
        py += 2.0
    if re.search(r'^\s*@\w+', sample, re.MULTILINE):
        py += 1.0
    if re.search(r'if __name__\s*==\s*["\']__main__["\']:', sample):
        py += 2.0
    if re.search(r'\b(self|__init__|__str__)\b', sample):
        py += 1.0
    if py > 0:
        score['python'] = py

    # C#
    cs = 0.0
    if re.search(r'^\s*using\s+System', sample, re.MULTILINE):
        cs += 3.0
    if re.search(r'^\s*namespace\s+\w+', sample, re.MULTILINE):
        cs += 3.0
    if re.search(r'\bpublic\s+(class|interface|struct|enum|record)\b', sample):
        cs += 2.0
    if re.search(r'\{ get; set; \}|\{ get; \}|\{ get; init; \}', sample):
        cs += 2.0
    if re.search(r'async\s+Task<|async\s+Task\s', sample):
        cs += 2.0
    if re.search(r'#region|#endregion|#pragma', sample):
        cs += 1.0
    if cs > 0:
        score['csharp'] = cs

    # Java
    jv = 0.0
    if re.search(r'^\s*package\s+[\w.]+\s*;', sample, re.MULTILINE):
        jv += 3.0
    if re.search(r'import\s+java\.', sample):
        jv += 3.0
    if re.search(r'import\s+javax\.', sample):
        jv += 2.0
    if re.search(r'\b(extends|implements)\b\s', sample):
        jv += 1.5
    if re.search(r'@Override|@Deprecated|@SuppressWarnings', sample):
        jv += 2.0
    if re.search(r'public\s+(static\s+)?void\s+main\s*\(', sample):
        jv += 2.0
    if re.search(r'(CompletableFuture|ArrayList|HashMap|JpaRepository|Serializable)\b', sample):
        jv += 1.0
    if re.search(r'\bList\s*<|Map\s*<|Set\s*<|Optional\s*<', sample):
        jv += 1.0
    if re.search(r'<\s*\w+\s+extends\s', sample):
        jv += 1.5
    if jv > 0:
        score['java'] = jv

    # C++
    cpp = 0.0
    if re.search(r'#include\s*[<"]', sample):
        cpp += 3.0
    if re.search(r'template\s*<', sample):
        cpp += 2.0
    if re.search(r'std::', sample):
        cpp += 2.0
    if re.search(r'#define|#pragma\s+once', sample):
        cpp += 1.0
    if re.search(r'\b(::\s*iterator|constexpr|noexcept|override|virtual)\b', sample):
        cpp += 1.0
    if cpp > 0:
        score['cpp'] = cpp

    # JavaScript
    js = 0.0
    if re.search(r'(const|let|var)\s+\w+\s*=\s*(require|import)\s*\(', sample):
        js += 3.0
    if re.search(r'(export\s+(default|const|function|class)|import\s+.*from\s+["\'])', sample):
        js += 2.0
    if re.search(r'=>\s*[{(]', sample):
        js += 1.5
    if re.search(r'console\.(log|error|warn)\s*\(', sample):
        js += 1.0
    if re.search(r'module\.exports\s*=|require\s*\(', sample):
        js += 2.0
    if js > 0:
        score['javascript'] = js

    # TypeScript (higher weight for TS-specific markers)
    ts = 0.0
    if re.search(r':\s*(string|number|boolean|void|any)\s*[=,;)\]]', sample):
        ts += 2.0
    if re.search(r'interface\s+\w+\s*\{', sample):
        ts += 2.0
    if re.search(r'type\s+\w+\s*=', sample):
        ts += 2.0
    if re.search(r'<(T|U|K|V)\s*(extends|,|>)', sample):
        ts += 1.0
    if re.search(r'as\s+(string|number|boolean|any|const)\b', sample):
        ts += 1.0
    if ts > 0:
        score['typescript'] = ts

    # Go
    go = 0.0
    if re.search(r'^\s*package\s+main\s*$', sample, re.MULTILINE):
        go += 3.0
    if re.search(r'import\s+["\']', sample):
        go += 2.0
    if re.search(r'\bfunc\s+\w+\s*\(', sample):
        go += 2.0
    if re.search(r'\bgo\s+\w+\s*\(', sample):
        go += 1.5
    if re.search(r'\bchan\b|\bdefer\b|\bgoroutine\b|\berrors\.', sample):
        go += 2.0
    if re.search(r'fmt\.(Print|Sprintf|Errorf)', sample):
        go += 1.0
    if go > 0:
        score['go'] = go

    # Rust
    rs = 0.0
    if re.search(r'^\s*(fn|pub\s+fn|pub\s+(struct|enum|trait|impl))', sample, re.MULTILINE):
        rs += 4.0  # boost from 3.0
    if re.search(r'->\s*\w+(<[^>]*>)?\s*\{', sample):
        rs += 1.5
    if re.search(r'\bmatch\s+\w+\s*\{', sample):
        rs += 2.0
    if re.search(r'\blet\s+mut\b', sample):
        rs += 1.5
    if re.search(r'use\s+\w+(::\w+)*;', sample):
        rs += 1.5
    if re.search(r'\b(impl|trait|struct|enum)\s+\w+\s*\{', sample):
        rs += 2.0
    if re.search(r'std::(collections|sync|vec|string|hash)', sample):
        rs += 2.0  # distinctly Rust std library
    if rs > 0:
        score['rust'] = rs

    # Kotlin
    kt = 0.0
    if re.search(r'^\s*package\s+[\w.]+', sample, re.MULTILINE):
        kt += 3.0  # package declaration is very Kotlin-specific
    if re.search(r'^\s*(fun|val|var)\s+\w+', sample, re.MULTILINE):
        kt += 3.0  # boost from 2.0
    if re.search(r'import\s+\w+\.\w+\.\*', sample):
        kt += 1.0
    if re.search(r'\b(suspend|inline|crossinline|noinline)\b', sample):
        kt += 2.0
    if re.search(r'^\s*typealias\s+\w+', sample, re.MULTILINE):
        kt += 2.0
    if re.search(r'\bkotlinx\.\w+', sample):
        kt += 3.0  # kotlinx.coroutines is distinctly Kotlin
    if kt > 0:
        score['kotlin'] = kt

    # SQL
    sql = 0.0
    # SQL statement starters (must be at line start or after semicolon)
    if re.search(r'(^|\;)\s*(SELECT|INSERT|CREATE|ALTER|DROP|UPDATE|DELETE)\b', sample, re.IGNORECASE | re.MULTILINE):
        sql += 3.0
    # SQL clauses - require typical SQL context (not in string imports)
    # Look for FROM followed by table name (not quoted string)
    if re.search(r'\bFROM\s+[\w.]+', sample, re.IGNORECASE):
        sql += 2.0
    if re.search(r'\bWHERE\b', sample, re.IGNORECASE):
        sql += 1.0
    if re.search(r'\b(JOIN|INNER JOIN|LEFT JOIN|RIGHT JOIN)\b', sample, re.IGNORECASE):
        sql += 2.0
    if re.search(r'\bGROUP BY\b', sample, re.IGNORECASE):
        sql += 1.5
    if re.search(r'\bORDER BY\b', sample, re.IGNORECASE):
        sql += 1.5
    if re.search(r'\bHAVING\b', sample, re.IGNORECASE):
        sql += 1.0
    # Semicolon as statement terminator (multiple statements or single statement ending)
    if re.search(r';\s*$', sample, re.MULTILINE):
        sql += 0.5
    if sql > 0:
        score['sql'] = sql

    if not score:
        return 'unknown'

    best_lang = max(score, key=score.get)
    best_score = score[best_lang]
    total = sum(score.values())
    if total == 0:
        return 'unknown'

    confidence = best_score / total

    # Strong single-keyword overrides for low confidence
    if confidence < 0.5:
        if '#include' in sample or 'std::' in sample:
            return 'cpp'
        if 'namespace ' in sample and 'using System' in sample:
            return 'csharp'
        if 'package ' in sample and 'import java.' in sample:
            return 'java'

    return best_lang


def _has_strong_language_markers(text: str, lang: str) -> bool:
    """
    Check if text has strong, unambiguous markers for a specific language.
    Used to override Pygments' generic 'Python' detection when fallback is confident.
    """
    sample = '\n'.join(text.split('\n')[:50])

    markers = {
        'java': [
            r'^\s*package\s+[\w.]+\s*;',
            r'import\s+java\.',
            r'\bpublic\s+class\b',
            r'\b(extends|implements)\b',
        ],
        'javascript': [
            r'import\s+.*from\s+[\'"]',
            r'export\s+(default|const|function|class)',
            r'require\s*\(',
            r'module\.exports\s*=',
        ],
        'typescript': [
            r'interface\s+\w+\s*\{',
            r'type\s+\w+\s*=',
            r':\s*(string|number|boolean|void|any)\s*[=,;)\]]',
        ],
        'go': [
            r'^\s*package\s+main\s*$',
            r'\bfunc\s+\w+\s*\(',
            r'import\s+[\'"]',
        ],
        'rust': [
            r'^\s*fn\s+\w+',
            r'^\s*pub\s+fn\s+\w+',
            r'\blet\s+mut\b',
            r'use\s+\w+(::\w+)*;',
        ],
        'kotlin': [
            r'^\s*fun\s+\w+',
            r'^\s*(val|var)\s+\w+',
            r'\bsuspend\b',
        ],
        'csharp': [
            r'^\s*using\s+System',
            r'^\s*namespace\s+\w+',
            r'\bpublic\s+class\b',
            r'\{ get; set; \}',
        ],
        'cpp': [
            r'#include\s*[<"]',
            r'std::',
            r'template\s*<',
        ],
        'sql': [
            r'^\s*(SELECT|INSERT|CREATE|ALTER|DROP|UPDATE|DELETE)\b',
            r'\b(FROM|WHERE|JOIN|GROUP BY|ORDER BY|HAVING)\b',
        ],
    }

    patterns = markers.get(lang, [])
    for pattern in patterns:
        if re.search(pattern, sample, re.MULTILINE | re.IGNORECASE):
            return True
    return False


def chunk_text(text: str) -> list[dict]:
    """
    Splits text into logical chunks with type labels.
    Each chunk: { 'content': str, 'type': 'code'|'conv', 'label': str }
    """
    chunks = []

    # Try to split on code block markers (```...```) first
    # Strictly bound to column 0 to prevent shredding string literals containing backticks
    code_fence_pattern = re.compile(r'(^```[\s\S]*?^```)', re.MULTILINE)
    parts = code_fence_pattern.split(text)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if part.startswith('```') and part.endswith('```'):
            # Explicit code fence — always code, full stop
            inner = part[3:-3].strip()
            lang_hint = inner.split('\n')[0].strip()
            chunks.append({
                'content': inner,
                'type': 'code',
                'label': f'CodeBlock:{lang_hint or "code"}'
            })
        else:
            # Split prose on conversation turns or function boundaries
            sub_chunks = _split_by_turns(part)
            chunks.extend(sub_chunks)

    # If nothing was split, treat the whole thing as one chunk
    # Guard: don't emit a block for empty input
    if not chunks and text.strip():
        ctype, _ = score_chunk(text)
        chunks.append({'content': text, 'type': ctype, 'label': 'Block:1'})

    return chunks


def _split_by_turns(text: str) -> list[dict]:
    """Split conversation turns OR function definitions."""

    # ── Conversation turn splitter ──────────────────────────────────────────
    # NOTE: inner group MUST be non-capturing (?:...) inside the lookahead.
    # A capturing group causes re.split() to inject the captured text
    # (e.g. 'Human', 'class') as extra list elements between the real chunks.
    turn_pattern = re.compile(
        r'(?=^(?:Human|Assistant|User|Claude|System|GPT|Me|You)\s*:)',
        re.MULTILINE | re.IGNORECASE
    )
    turns = turn_pattern.split(text)
    turns = [t.strip() for t in turns if t.strip()]

    if len(turns) > 1:
        result = []
        for i, turn in enumerate(turns):
            # Each turn: run through score_chunk — if it has heavy code content
            # (e.g. a fenced block inside a chat) classify it code, not conv.
            ctype, conf = score_chunk(turn)
            # Conv turns usually have near-zero code signal; if code dominant, trust it
            label_type = ctype if ctype == 'code' else 'conv'
            result.append({
                'content': turn,
                'type': label_type,
                'label': f'Turn:{i+1}',
            })
        return result

    # ── Language-agnostic function/class/type splitter ──────────────────────
    # Covers Python (def/class), JS/TS (function/const/let/var), C#/Java
    # (access modifiers + type keywords), C++ (template/struct/class),
    # Go (func), Rust (fn)
    func_pattern = re.compile(
        r'^\s*(?='
        r'def |async def |class\s+\w|function |'
        r'(?:(?:public|private|protected|internal|static|virtual|abstract|sealed|readonly)\s+)*(?:class|interface|struct|enum|record)\s+\w|'
        r'template\s*<|'
        r'func\s+\w+\s*\(|'
        r'fn\s+\w+|'
        r'(?:const|let|var)\s+\w+\s*='
        r')',
        re.MULTILINE
    )
    # ── Check for open try/except/with/multi-line parens before splitting ──
    # This prevents splitting inside multi-line control flow (e.g. a try/except
    # with a function definition inside the except body), which would produce
    # a syntactically invalid block (except line orphaned from its body).
    # Type declaration boundaries (class/interface/struct/enum) are ALLOWED
    # even inside open braces (e.g. inside a namespace or outer class).
    TYPE_KW = re.compile(r'(class|interface|struct|enum|record)\s')
    boundaries = []
    for m in func_pattern.finditer(text):
        pos = m.start()
        # Check if this match is a type declaration boundary — always allow
        is_type_boundary = bool(TYPE_KW.search(text[m.start():m.end() + 20]))
        if not is_type_boundary:
            prefix = text[:pos]
            # Check for unclosed try/except blocks
            try_count = len(re.findall(r'\btry\s*:', prefix))
            except_count = len(re.findall(r'\bexcept\b', prefix))
            # Check for unclosed parentheses/brackets/braces
            open_parens = prefix.count('(') - prefix.count(')')
            open_brackets = prefix.count('[') - prefix.count(']')
            open_braces = prefix.count('{') - prefix.count('}')
            if try_count > except_count:
                continue
            if open_parens > 0 or open_brackets > 0 or open_braces > 0:
                continue
        boundaries.append(pos)

    if boundaries:
        funcs = []
        prev = 0
        for b in boundaries:
            funcs.append(text[prev:b])
            prev = b
        funcs.append(text[prev:])
        funcs = [f.strip() for f in funcs if f.strip()]
    else:
        funcs = [text.strip()] if text.strip() else []

    if len(funcs) > 1:
        result = []
        for i, func in enumerate(funcs):
            first_line = func.split('\n')[0].strip()
            # FIX: if first line is a code definition keyword, force 'code'
            # instead of trusting score_chunk (which can be fooled by comments/strings)
            if _CODE_FIRST_LINE.match(first_line):
                ctype = 'code'
            else:
                ctype, _ = score_chunk(func)

            result.append({
                'content': func,
                'type': ctype,
                'label': f'Block:{first_line[:40]}',
            })

        # Enforce minimum block size (2 lines) — merge 1-line blocks
        merged = []
        for chunk in result:
            lines = chunk['content'].count('\n') + 1
            if merged and lines < 2 and merged[-1]['type'] == chunk['type']:
                merged[-1]['content'] += '\n' + chunk['content']
                merged[-1]['label'] += ' + ' + chunk['label']
            else:
                merged.append(chunk)
        result = merged

        # Enforce maximum block size (150 lines) — split oversized blocks
        MAX_BLOCK_LINES = 150
        split_result = []
        for chunk in result:
            lines = chunk['content'].count('\n') + 1
            if lines <= MAX_BLOCK_LINES:
                split_result.append(chunk)
            else:
                content_lines = chunk['content'].split('\n')
                for start in range(0, len(content_lines), MAX_BLOCK_LINES):
                    sub = '\n'.join(content_lines[start:start + MAX_BLOCK_LINES])
                    split_result.append({
                        'content': sub,
                        'type': chunk['type'],
                        'label': f"{chunk['label']}:{start // MAX_BLOCK_LINES + 1}",
                    })
        return split_result

    # ── Fallback: single undifferentiated block ─────────────────────────────
    ctype, _ = score_chunk(text)
    return [{'content': text, 'type': ctype, 'label': 'Block:1'}]


def detect_style(text: str, lang: str) -> str:
    """
    Detect code style: 'oop', 'functional', 'vibe', or 'mixed'.
    """
    oop_score = 0
    functional_score = 0
    vibe_score = 0

    # OOP signals
    if 'class ' in text:
        oop_score += 1
    if 'self.' in text:
        oop_score += 1
    if '__init__' in text:
        oop_score += 1
    if re.search(r'\.\w+\s*\(', text):
        oop_score += 1

    # Functional signals
    if 'lambda' in text:
        functional_score += 1
    if 'map(' in text:
        functional_score += 1
    if 'filter(' in text:
        functional_score += 1
    if 'reduce(' in text:
        functional_score += 1
    if re.search(r'\[[^\]]*for[^\]]*in[^\]]*\]', text):
        functional_score += 1
    if re.search(r'\([^)]*for[^)]*in[^)]*\)', text):
        functional_score += 1

    # Vibe signals
    idents = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text)
    if idents:
        avg_len = sum(len(i) for i in idents) / len(idents)
        if avg_len < 4:
            vibe_score += 1

    lines = text.split('\n')
    non_empty_lines = [l for l in lines if l.strip()]
    total_lines = len(non_empty_lines)
    if total_lines > 0:
        comment_count = 0
        for line in non_empty_lines:
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('//') or '/*' in stripped or '*/' in stripped:
                comment_count += 1
        if comment_count < total_lines / 20:
            vibe_score += 1

        ternary_count = 0
        for line in non_empty_lines:
            stripped = line.strip()
            if ' if ' in stripped and ' else ' in stripped:
                if not stripped.startswith(('if ', 'elif ', 'else:', 'def ', 'class ', 'for ', 'while ')):
                    ternary_count += 1
            elif re.search(r'\?\s*[^?{[\]]+?:', stripped):
                ternary_count += 1
        if ternary_count / total_lines > 0.3:
            vibe_score += 1

    scores = {'oop': oop_score, 'functional': functional_score, 'vibe': vibe_score}
    max_score = max(scores.values())
    top = [k for k, v in scores.items() if v == max_score]

    if len(top) == 1:
        return top[0]
    return 'mixed'
