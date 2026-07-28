"""
grid.py — Layer 5: Deterministic Center-Out Grid Placement

Rules:
  - 32×32 grid (expands by +8 cells on each axis when literally no room for next block)
  - Each block is 4×4 cells; blue (minor) blocks are 2×2 cells
  - Placement is center-out spiral, sorted by block ID (ascending)
  - No physics, no force simulation, no randomness
  - Same input → same hash → identical layout every time

Public API (called by compress.py):
  place_blocks(blocks, grid_size=32)           → (list[dict] with grid_pos set, final_grid_size)
  build_connection_index(blocks)               → dict[block_id, list[connected_id]]
  check_expansion_needed(blocks, grid_size)    → bool
  expand_grid(current_grid_size, blocks)       → int (new grid size)
  grid_positions_dict(blocks)                  → dict[block_id, [row, col]]
  place_minor_block(connects_to, block_positions) → [row, col]
  format_connection_index(conn_index)          → str  (for @x line in ctxpack)

Connection index format for @x ctxpack section:
  @x b1:b3,b7 b2:b5 b4:b1,b2
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

# ── Grid constants ─────────────────────────────────────────────────────────────
BLOCK_SIZE   = 4    # code and conv blocks are always 4×4 cells
MINOR_SIZE   = 2    # minor (blue) blocks are always 2×2 cells
EXPAND_STEP  = 8    # cells added to each axis on expansion (32→40→48 etc.)
INITIAL_SIZE = 32   # starting grid size


# ── Occupancy helpers ──────────────────────────────────────────────────────────

def _block_size_for(block: dict) -> int:
    """Return the cell size for this block: 4 for code/conv, 2 for minor."""
    return MINOR_SIZE if block.get("type") == "minor" else BLOCK_SIZE


def _footprint_cells(row: int, col: int, sz: int) -> Set[Tuple[int, int]]:
    """All grid cells occupied by a sz×sz block at (row, col)."""
    cells: Set[Tuple[int, int]] = set()
    for dr in range(sz):
        for dc in range(sz):
            cells.add((row + dr, col + dc))
    return cells


def _footprint_with_buffer(row: int, col: int, sz: int) -> Set[Tuple[int, int]]:
    """All grid cells occupied by a sz×sz block PLUS a 1-cell buffer around it."""
    cells: Set[Tuple[int, int]] = set()
    for dr in range(-1, sz + 1):
        for dc in range(-1, sz + 1):
            cells.add((row + dr, col + dc))
    return cells


def _can_place(row: int, col: int, sz: int, occupied: Set[Tuple[int, int]], grid_size: int) -> bool:
    """True iff the sz×sz block fits inside grid_size and overlaps no occupied cell."""
    if row < 0 or col < 0:
        return False
    if row + sz > grid_size or col + sz > grid_size:
        return False
    return _footprint_cells(row, col, sz).isdisjoint(occupied)


def _center_origin(grid_size: int, sz: int) -> Tuple[int, int]:
    """Top-left (row, col) of the exact center slot for a sz×sz block."""
    return grid_size // 2 - sz // 2, grid_size // 2 - sz // 2


# ── Spiral slot generator ──────────────────────────────────────────────────────

def _spiral_slots(anchor_row: int, anchor_col: int, grid_size: int, sz: int) -> List[Tuple[int, int]]:
    """
    Generate candidate (row, col) placements in Chebyshev-distance order
    outward from (anchor_row, anchor_col).

    The anchor is the center slot; each ring radiates outward.
    For a given radius R, produces all (row, col) with Chebyshev distance
    exactly R from anchor, ordered clockwise starting from top-left.
    """
    slots: List[Tuple[int, int]] = [(anchor_row, anchor_col)]
    max_radius = grid_size  # upper bound — we cover the whole grid
    for radius in range(1, max_radius + 1):
        # Walk the perimeter of the Chebyshev square at this radius
        # Top row: left→right
        row = anchor_row - radius
        for dc in range(-radius, radius + 1):
            col = anchor_col + dc
            if 0 <= row and row + sz <= grid_size and 0 <= col and col + sz <= grid_size:
                slots.append((row, col))
        # Right column: top→bottom (skip corners)
        col = anchor_col + radius
        for dr in range(-radius + 1, radius):
            row = anchor_row + dr
            if 0 <= row and row + sz <= grid_size and 0 <= col and col + sz <= grid_size:
                slots.append((row, col))
        # Bottom row: right→left
        row = anchor_row + radius
        for dc in range(radius, -radius - 1, -1):
            col = anchor_col + dc
            if 0 <= row and row + sz <= grid_size and 0 <= col and col + sz <= grid_size:
                slots.append((row, col))
        # Left column: bottom→top (skip corners)
        col = anchor_col - radius
        for dr in range(radius - 1, -radius, -1):
            row = anchor_row + dr
            if 0 <= row and row + sz <= grid_size and 0 <= col and col + sz <= grid_size:
                slots.append((row, col))

    # Deduplicate while preserving order
    seen: Set[Tuple[int, int]] = set()
    result: List[Tuple[int, int]] = []
    for s in slots:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


# ── Connection / adjacency index ───────────────────────────────────────────────

def build_connection_index(blocks: list[dict]) -> dict[str, list[str]]:
    """
    Build a bidirectional adjacency map from HeatResult import/call signals.

    Two blocks are considered related when any of:
      • Block A calls a name that block B imports or defines
      • Block B calls a name that block A imports or defines
      • Both blocks import the same name (shared dependency)

    Returns:
        { block_id: [connected_block_id, ...] }
        Only blocks that have at least one connection are included.
    """
    vocab: dict[str, dict[str, set[str]]] = {}

    for b in blocks:
        bid = b.get("id", "")
        heat = b.get("heat")
        if heat is not None:
            imports = set(getattr(heat, "block_imports", None) or [])
            calls   = set(getattr(heat, "block_calls",   None) or [])
        else:
            imports = set(b.get("block_imports", []))
            calls   = set(b.get("block_calls",   []))
        vocab[bid] = {"imports": imports, "calls": calls, "all": imports | calls}

    adj: dict[str, set[str]] = {b["id"]: set() for b in blocks}
    ids = [b["id"] for b in blocks]

    for i, id_a in enumerate(ids):
        va = vocab.get(id_a, {})
        for j, id_b in enumerate(ids):
            if i >= j:
                continue
            vb = vocab.get(id_b, {})
            related = (
                bool(va.get("calls",   set()) & vb.get("all",     set()))
                or bool(vb.get("calls",   set()) & va.get("all",     set()))
                or bool(va.get("imports", set()) & vb.get("imports", set()))
            )
            if related:
                adj[id_a].add(id_b)
                adj[id_b].add(id_a)

    return {bid: sorted(neighbours) for bid, neighbours in adj.items() if neighbours}


# ── Public API ─────────────────────────────────────────────────────────────────

def check_expansion_needed(blocks: list[dict], grid_size: int) -> bool:
    """
    Return True when the grid is actually full — i.e. a 4×4 block has no
    available slot anywhere on the current grid. Never expands speculatively.
    """
    occupied: Set[Tuple[int, int]] = set()
    for b in blocks:
        pos = b.get("grid_pos")
        if pos and len(pos) >= 2:
            sz = _block_size_for(b)
            occupied.update(_footprint_with_buffer(pos[0], pos[1], sz))

    # Check if there's any room for the largest block type (4×4)
    center_row, center_col = _center_origin(grid_size, BLOCK_SIZE)
    for row, col in _spiral_slots(center_row, center_col, grid_size, BLOCK_SIZE):
        if _can_place(row, col, BLOCK_SIZE, occupied, grid_size):
            return False  # still room
    return True  # literally no room left


def expand_grid(current_grid_size: int, blocks: list[dict]) -> int:
    """
    Add EXPAND_STEP (8) to each axis → grid grows by 8 total.
    Existing positions stay unchanged (new space is added to the right/bottom
    edge — the center-out spiral will naturally fill new slots).
    Returns the new grid size integer.
    """
    return current_grid_size + EXPAND_STEP


def place_blocks(blocks: list[dict], grid_size: int = INITIAL_SIZE) -> tuple[list[dict], int]:
    """
    Assign grid_pos [row, col] to every block in-place.

    Algorithm:
      1. Sort all blocks by ID (ascending) — deterministic order.
      2. First block goes in the exact center cell.
      3. Each subsequent block takes the next available slot in the
         center-out Chebyshev spiral, skipping occupied cells.
      4. If no slot exists, expand the grid by EXPAND_STEP and retry.
      5. Minor (2×2) blocks use a 2×2 footprint; code/conv use 4×4.

    Determinism: same block IDs → same sort order → same spiral position → pixel-identical layout.
    No randomness. No force simulation.

    Returns:
        (blocks, final_grid_size) — blocks with grid_pos set, and the actual grid size
        after any automatic expansions.
    """
    if not blocks:
        return blocks, grid_size

    import logging
    logger = logging.getLogger(__name__)

    occupied: Set[Tuple[int, int]] = set()

    # ── Re-register already-placed blocks (accumulation support) ──
    for b in blocks:
        if b.get("grid_pos"):
            r, c = b["grid_pos"][0], b["grid_pos"][1]
            sz = _block_size_for(b)
            footprint = _footprint_with_buffer(r, c, sz)
            occupied.update(footprint)
    
    logger.info("Grid start: occupied_cells=%d, initial_grid_size=%d", len(occupied), grid_size)

    type_order = {"conv": 0, "code": 1, "minor": 2}

    to_place = sorted(
        [b for b in blocks if not b.get("grid_pos")],
        key=lambda x: (type_order.get(x.get("type", "code"), 1), x.get("id", ""))
    )
    if not to_place:
        return blocks, grid_size

    for b in to_place:
        sz = _block_size_for(b)

        while True:
            center_row, center_col = _center_origin(grid_size, sz)
            spiral = _spiral_slots(center_row, center_col, grid_size, sz)
            placed = False
            for row, col in spiral:
                if _can_place(row, col, sz, occupied, grid_size):
                    b["grid_pos"] = [row, col]
                    occupied.update(_footprint_with_buffer(row, col, sz))
                    placed = True
                    break
            if placed:
                break
            # Grid is full — expand and retry
            grid_size = expand_grid(grid_size, blocks)

    logger.info("Grid end: occupied_cells=%d, final_grid_size=%d", len(occupied), grid_size)
    return blocks, grid_size


def place_minor_blocks(minor_blocks: list[dict], blocks: list[dict], grid_size: int) -> tuple[list[dict], int]:
    """
    Place blue connection (minor) blocks near the geometric centroid of the
    code blocks they connect, avoiding exclusion zones of other blocks.

    Args:
        minor_blocks: List of minor block dicts to place.
        blocks:       Already placed main blocks (for exclusion zones).
        grid_size:    Current grid size.

    Returns:
        (minor_blocks, final_grid_size)
    """
    if not minor_blocks:
        return minor_blocks, grid_size

    occupied: Set[Tuple[int, int]] = set()
    for b in blocks:
        if b.get("grid_pos"):
            r, c = b["grid_pos"][0], b["grid_pos"][1]
            sz = _block_size_for(b)
            occupied.update(_footprint_with_buffer(r, c, sz))

    block_positions = grid_positions_dict(blocks)

    minor_blocks = sorted(minor_blocks, key=lambda x: x.get("id", ""))

    for mb in minor_blocks:
        connects_to = mb.get("connects_to", [])
        rows: list[int] = []
        cols: list[int] = []
        for bid in connects_to:
            pos = block_positions.get(bid)
            if pos:
                rows.append(pos[0] + BLOCK_SIZE // 2)
                cols.append(pos[1] + BLOCK_SIZE // 2)
        
        if rows:
            anchor_row = int(sum(rows) / len(rows))
            anchor_col = int(sum(cols) / len(cols))
        else:
            anchor_row, anchor_col = _center_origin(grid_size, MINOR_SIZE)

        sz = MINOR_SIZE
        while True:
            spiral = _spiral_slots(anchor_row, anchor_col, grid_size, sz)
            placed = False
            for r, c in spiral:
                if _can_place(r, c, sz, occupied, grid_size):
                    mb["grid_pos"] = [r, c]
                    occupied.update(_footprint_with_buffer(r, c, sz))
                    placed = True
                    break
            if placed:
                break
            grid_size = expand_grid(grid_size, blocks + minor_blocks)

    return minor_blocks, grid_size


def center_layout(blocks: list[dict], grid_size: int) -> int:
    """
    Checks if the bounding box of all placed blocks is off-center by > 2 cells.
    If so, translates all block positions to perfectly center the layout.
    """
    valid_blocks = [b for b in blocks if b.get("grid_pos")]
    if not valid_blocks:
        return grid_size

    min_r = min(b["grid_pos"][0] for b in valid_blocks)
    max_r = max(b["grid_pos"][0] + _block_size_for(b) for b in valid_blocks)
    min_c = min(b["grid_pos"][1] for b in valid_blocks)
    max_c = max(b["grid_pos"][1] + _block_size_for(b) for b in valid_blocks)

    box_center_r = (min_r + max_r) / 2
    box_center_c = (min_c + max_c) / 2

    # Math exact grid centers
    grid_center_r = grid_size / 2
    grid_center_c = grid_size / 2

    shift_r = round(grid_center_r - box_center_r)
    shift_c = round(grid_center_c - box_center_c)

    if abs(shift_r) > 2 or abs(shift_c) > 2:
        for b in valid_blocks:
            b["grid_pos"][0] += int(shift_r)
            b["grid_pos"][1] += int(shift_c)
            
        # check if it breaches boundary and expand if necessary
        new_max_r = max_r + shift_r
        new_max_c = max_c + shift_c
        while new_max_r > grid_size or new_max_c > grid_size:
            grid_size = expand_grid(grid_size, blocks)

    return grid_size


def format_connection_index(conn_index: dict[str, list[str]]) -> str:
    """
    Serialise a connection index to the @x ctxpack line format.

    Example output:  b1:b3,b7 b2:b5 b4:b1,b2
    Returns an empty string if conn_index is empty (caller omits the @x line).
    """
    if not conn_index:
        return ""
    parts: list[str] = []
    for bid in sorted(conn_index.keys()):
        neighbours = sorted(conn_index[bid])
        if neighbours:
            parts.append(f"{bid}:{','.join(neighbours)}")
    return " ".join(parts)


def grid_positions_dict(blocks: list[dict]) -> dict[str, list[int]]:
    """
    Extract { block_id: [row, col] } from a list of placed blocks.
    Blocks without a grid_pos are silently skipped.
    """
    return {
        b["id"]: list(b["grid_pos"])
        for b in blocks
        if b.get("id") and b.get("grid_pos")
    }
