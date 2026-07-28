# nemori package
from .analyzer import chunk_text, detect_language, score_chunk, detect_style
from .competition import compete_block, compete_blocks
from .ctxpack import assemble, parse, preview
from .decompressor import decompress, verify_round_trip
from .heatmap import scan_block, scan_blocks, HeatResult
from .grid import (
    place_blocks, expand_grid, build_connection_index, format_connection_index,
    check_expansion_needed, grid_positions_dict, place_minor_blocks, center_layout,
)
from .tokens import count_tokens, net_gain
from .conv_compress import light_touch_compress
from .fingerprint import fingerprint_chunk, find_minor_patterns, get_raw_hash
from .sentinel import check_final, check_layer

__version__ = "0.1.0"
__all__ = [
    'chunk_text', 'detect_language', 'score_chunk', 'detect_style',
    'compete_block', 'compete_blocks',
    'assemble', 'parse', 'preview',
    'decompress', 'verify_round_trip',
    'scan_block', 'scan_blocks', 'HeatResult',
    'place_blocks', 'expand_grid', 'build_connection_index', 'format_connection_index',
    'check_expansion_needed', 'grid_positions_dict', 'place_minor_blocks', 'center_layout',
    'count_tokens', 'net_gain',
    'light_touch_compress',
    'fingerprint_chunk', 'find_minor_patterns', 'get_raw_hash',
    'check_final', 'check_layer',
]
