# Nemori Engine (Preview / Core Teaser)

> [!NOTE]
> **Open Source Teaser Note:** This repository represents a preview showcasing **~30% of the core architecture** behind Nemori. The full proprietary engine includes additional multi-file project AST graphs, multi-layered dictionary alias resolution, neural strategy learning, and specialized language transformers that are under active development.

Nemori Engine is a lightweight Python library containing the core compression pipeline of Nemori. It compresses source code and AI conversation histories into `.ctxpack` files, reducing LLM token consumption by 40% to 70% while remaining directly readable by AI models like Anthropic's Claude.

## How it works

The engine passes input through a deterministic multi-stage compression pipeline:

1. **Semantic Chunking & Scope Isolation** — Splits source code and multi-turn conversations into distinct structural blocks based on AST boundaries (`analyzer.py`).
2. **Multi-Strategy Competition** — Evaluates multiple compression strategies per block in parallel and selects the transformation that yields the minimum BPE token count (`competition.py`).
3. **Deterministic 2D Spatial Placement** — Maps code blocks into a 2D topology index (`@x`) using Chebyshev spiral searching to encode inter-block call relationships (`grid.py`).
4. **Sentinel Integrity Validation** — Verifies AST safety and automatically rolls back any transformation stage that yields negative token gains (`sentinel.py`).
5. **Context Serialization** — Assembles all header directives, block topologies, and encoded strings into the compact `.ctxpack` specification (`ctxpack.py`).

## The @-spec format

The `.ctxpack` format is a structured specification optimized for LLM attention mechanisms. AI models can process `.ctxpack` files directly without prior decompression.

```ctxpack
@s python
@u import os,sys,typing
@t T=Dict[str,Any]
@m a1=process_request a2=payload_data
@sig s1=def main(config: T) -> None:
@b 1C
def run():
    a1(a2)
@x b1:b2
```

### Directives Reference
* `@s` — Target language specification.
* `@u` — Collapsed imports and dependencies.
* `@t` — Type alias definitions.
* `@m` — Identifier substitution map.
* `@sig` / `@lam` / `@i` — Extracted signatures, lambdas, and idioms.
* `@b` — Block boundary tag (`C` for Code, `V` for Conversation).
* `@x` — Spatial adjacency and dependency index across blocks.

## Quick start

```python
from nemori import decompress, assemble, parse

# Decompress a .ctxpack file back to original source code
original_code = decompress(ctxpack_content)
```

## Benchmarks

| Input Type | Original Tokens | Compressed Tokens | Reduction |
|---|---|---|---|
| Python Class (50 lines) | ~400 | ~180 | 55% |
| JavaScript Module (100 lines) | ~800 | ~320 | 60% |
| AI Conversation (20 turns) | ~1,200 | ~720 | 40% |
| Mixed Codebase (500 lines) | ~4,000 | ~1,200 | 70% |

*Note: Benchmarks reflect core pipeline performance. Additional proprietary layers achieve higher compression ratios on large-scale codebases.*

## Supported languages

Language-aware chunking and token evaluation support:
* Python
* JavaScript
* TypeScript
* C#
* Java
* Go
* Rust
* C++ / C
* Kotlin
* SQL

## Status

This public sneak peek represents an early preview of the engine architecture (~30% of full capability). Built and maintained by a solo developer for the **Claude for Open Source** program.

## License

[MIT](LICENSE)
