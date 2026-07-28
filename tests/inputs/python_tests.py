"""
Nemori Engine Test File — Python
Tests every engine feature that applies to Python code.

Features tested by this file:
  L0.5  preprocess: strip_namespace (docstring collapse), strip_access_modifiers (N/A for python), property_shorthand (N/A), expression_body (N/A)
  L1a   minify: strip_block_comments, strip_inline_comments, collapse_blank_lines, reduce_python_indent, strip_operator_spaces
  L1b   @m substitution: frequency-ordered aliases, collision guard, method guard, string literal protection
  L1c   @u import collapse: from X import Y, import X
  L1d   @t type aliases: DT, TD, CL, IT, FN, TP, DC, PB, AIO, SC, TH
  L1e   @g generic inference: N/A for Python generics (no angle-bracket generics)
  Item7 @p pattern dictionary: repeated n-grams across functions
  Item8 @b block dedup: identical function bodies
  Item11 @c conversation compression: N/A (pure code)
  Item16 @i idiom dictionary: g0 (guard clause None), g1 (falsy guard), t0 (try-except), e0 (__eq__+__hash__)
  @sig  method signature dedup: repeated def signatures (need 3+ occurrences)
  @lam  lambda consolidation: repeated lambda expressions (need 3+ occurrences)
"""

import os
import sys
import json
import hashlib
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from collections import defaultdict, OrderedDict
from pathlib import Path
from datetime import datetime, timedelta
import asyncio
import logging

# =====================================================================
# SECTION 1: @t Type Alias Candidates
# =====================================================================
# These types appear in the Python @t pre-seeded table:
#   DT=datetime, TZ=timezone, TD=timedelta, CL=collections, IT=itertools,
#   FN=functools, TP=typing, DC=dataclasses, PB=pathlib, AIO=asyncio,
#   SC=subprocess, TH=threading

def uses_type_aliases():
    dt = datetime.now()
    td = timedelta(days=7)
    tz = dt.tzinfo
    pb = Path("/tmp/test")
    dc_list: List[str] = []
    tp_dict: Dict[str, int] = {}
    aio_loop = asyncio.new_event_loop()
    sc_result = None
    th_thread = None
    fn_reduce = None
    it_chain = None
    cl_defaultdict = defaultdict(list)
    return dt, td, tz, pb, dc_list, tp_dict, aio_loop, sc_result, th_thread, fn_reduce, it_chain, cl_defaultdict


# =====================================================================
# SECTION 2: @u Import Collapse Candidates (3+ import lines needed)
# =====================================================================
# These will be collapsed into @u section:
#   import os
#   import sys
#   import json
#   import hashlib
#   from typing import List, Dict, Optional
#   from dataclasses import dataclass
# (already imported at top of file — this section is for testing within function scope)
def import_heavy_function():
    import os
    import sys
    import json
    import hashlib
    from typing import List, Dict, Optional
    from dataclasses import dataclass
    return os, sys, json, hashlib


# =====================================================================
# SECTION 3: @m Substitution Candidates (long, repeated identifiers)
# =====================================================================
# These identifiers appear multiple times with long names — prime candidates
# for @m alias substitution:
#   connection_pool_manager (3x)
#   active_connection_list (3x)
#   max_connection_count (2x)
#   initialize_connection_pool (2x)
#   process_connection_request (2x)

class ConnectionPoolManager:
    def __init__(self, max_connection_count):
        self.active_connection_list = []
        self.max_connection_count = max_connection_count

    def initialize_connection_pool(self):
        for i in range(self.max_connection_count):
            conn = self.create_connection()
            self.active_connection_list.append(conn)

    def create_connection(self):
        return {"status": "open", "id": len(self.active_connection_list)}

    def process_connection_request(self, request):
        if not self.active_connection_list:
            self.initialize_connection_pool()
        conn = self.active_connection_list.pop()
        result = self.handle_request(conn, request)
        self.active_connection_list.append(conn)
        return result

    def handle_request(self, conn, request):
        return {"conn": conn, "request": request, "processed": True}

    def get_all_active_sessions(self):
        return [c for c in self.active_connection_list]

    def shutdown_connection_pool(self):
        for conn in self.active_connection_list:
            conn["status"] = "closed"
        self.active_connection_list.clear()


# =====================================================================
# SECTION 4: @p Pattern Dictionary Candidates
# =====================================================================
# This pattern appears 4 times across functions — should be extracted:
#   "connection_pool_manager.get_connection()"

def pattern_function_alpha():
    connection_pool_manager = ConnectionPoolManager(10)
    conn = connection_pool_manager.get_all_active_sessions()
    result_a = conn[0] if conn else None
    return result_a

def pattern_function_beta():
    connection_pool_manager = ConnectionPoolManager(5)
    conn = connection_pool_manager.get_all_active_sessions()
    result_b = conn[0] if conn else None
    return result_b

def pattern_function_gamma():
    connection_pool_manager = ConnectionPoolManager(8)
    conn = connection_pool_manager.get_all_active_sessions()
    result_c = conn[0] if conn else None
    return result_c

def pattern_function_delta():
    connection_pool_manager = ConnectionPoolManager(3)
    conn = connection_pool_manager.get_all_active_sessions()
    result_d = conn[0] if conn else None
    return result_d


# =====================================================================
# SECTION 5: Block Dedup Candidates (identical function bodies)
# =====================================================================

def identical_function_one(connection_string):
    parsed = parse_connection_string(connection_string)
    validated = validate_parsed(parsed)
    return create_pool(validated)

def identical_function_two(connection_string):
    parsed = parse_connection_string(connection_string)
    validated = validate_parsed(parsed)
    return create_pool(validated)

def identical_function_three(connection_string):
    parsed = parse_connection_string(connection_string)
    validated = validate_parsed(parsed)
    return create_pool(validated)

def parse_connection_string(s):
    return {"raw": s, "parts": s.split(":")}

def validate_parsed(p):
    return {"valid": True, "data": p}

def create_pool(v):
    return {"pool": v, "ready": True}


# =====================================================================
# SECTION 6: @i Idiom Dictionary Candidates
# =====================================================================

# g0: Guard clause None check (Python)
def process_user_data(user_data):
    if user_data is None:
        return None
    return {"processed": user_data}

# g1: Guard clause falsy check (Python)
def validate_input(input_value):
    if not input_value:
        return False
    return True

# g0 repeated
def handle_callback(callback_data):
    if callback_data is None:
        return None
    return {"handled": callback_data}

# g0 repeated again
def transform_result(result_data):
    if result_data is None:
        return None
    return {"transformed": result_data}

# g1 repeated
def check_permission(permission_data):
    if not permission_data:
        return False
    return True

# g1 repeated again
def verify_token(token_data):
    if not token_data:
        return False
    return True


# =====================================================================
# SECTION 7: @sig Method Signature Dedup Candidates (3+ identical signatures)
# =====================================================================
# Need 3+ functions with the same signature pattern

def calculate_metric(data_point: float, window_size: int) -> float:
    return data_point * window_size

def calculate_average(data_point: float, window_size: int) -> float:
    return data_point / max(window_size, 1)

def calculate_maximum(data_point: float, window_size: int) -> float:
    return max(data_point, window_size)


# =====================================================================
# SECTION 8: @lam Lambda Consolidation Candidates (3+ identical lambdas)
# =====================================================================

def apply_lambda_operations():
    items = [(1, 'a'), (2, 'b'), (3, 'c'), (4, 'd'), (5, 'e')]
    # Same lambda appearing 3+ times
    mapped1 = list(map(lambda x: x[0], items))
    filtered = list(filter(lambda x: x[0] > 2, items))
    sorted_items = sorted(items, key=lambda x: x[0])
    return mapped1, filtered, sorted_items


# =====================================================================
# SECTION 9: String Literal Protection
# =====================================================================
# Identifiers inside strings must NOT be substituted

def string_literal_test():
    active_connection_list = "active_connection_list is a variable"
    max_connection_count = 'max_connection_count appears in single quotes'
    template = f"The active_connection_list has max_connection_count items"
    return active_connection_list, max_connection_count, template


# =====================================================================
# SECTION 10: Method Guard (lowercase method calls not aliased)
# =====================================================================

class MethodGuardTest:
    def process_connection_request(self, data):
        return data

    def initialize_connection_pool(self):
        return True

    def get_all_active_sessions(self):
        return []

    def test_method_guard(self):
        self.process_connection_request("test")
        self.initialize_connection_pool()
        self.get_all_active_sessions()
        return True


# =====================================================================
# SECTION 11: Operator Spacing Minification
# =====================================================================

def operator_spacing_test(a, b, c):
    x = a + b
    y = b - c
    z = a * b
    w = a / max(c, 1)
    result = x + y + z + w
    is_greater = result > 100
    is_equal = result == 100
    return result, is_greater, is_equal


# =====================================================================
# SECTION 12: Minification — Comments, Blank Lines, Indentation
# =====================================================================
# This function has:
#   - inline comments that should be stripped
#   - blank lines that should be collapsed
#   - 4-space indentation that should be reduced to 1-space

def minification_test():
    # This is an inline comment that should be stripped
    x = 1
    y = 2

    # Another comment
    z = x + y

    """This docstring should be stripped by block comment removal."""


    # Comment after blank lines
    for i in range(10):
        # Loop comment
        if i % 2 == 0:
            result = i * 2
        else:
            result = i * 3
    return z


# =====================================================================
# SECTION 13: Decorator and Complex Syntax
# =====================================================================

def decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@decorator
def decorated_function(x, y):
    return x + y

# List comprehension (functional signal)
squares = [x**2 for x in range(10)]
evens = list(filter(lambda x: x % 2 == 0, range(20)))
mapped = list(map(lambda x: x * 2, range(10)))


# =====================================================================
# SECTION 14: Complex Data Structures (test fingerprint stability)
# =====================================================================

COMPLEX_CONFIG = {
    "database": {
        "host": "127.0.0.1",
        "port": 5432,
        "name": "nemori_test",
        "pool_size": 10,
    },
    "cache": {
        "backend": "redis",
        "ttl": 3600,
        "max_size": 1000,
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    },
}


# =====================================================================
# SECTION 15: Nested Control Flow (test block boundary detection)
# =====================================================================

def nested_control_flow(data):
    results = []
    for item in data:
        try:
            if isinstance(item, dict):
                for key, value in item.items():
                    if value is not None:
                        if isinstance(value, str):
                            results.append(value.strip())
                        elif isinstance(value, (int, float)):
                            results.append(str(value))
                    else:
                        continue
            elif isinstance(item, list):
                results.extend([str(x) for x in item if x is not None])
            else:
                results.append(str(item))
        except (TypeError, ValueError) as e:
            logging.error(f"Error processing {item}: {e}")
            continue
        finally:
            pass
    return results


# =====================================================================
# SECTION 16: Guard Clause Patterns (for @i idiom dict)
# =====================================================================

# Additional g0 (None check) instances — already have 3 above, adding more
def guard_none_a(value):
    if value is None:
        return None
    return value * 2

def guard_none_b(value):
    if value is None:
        return None
    return value + 1

# Additional g1 (falsy check) instances
def guard_falsy_a(flag):
    if not flag:
        return False
    return True

def guard_falsy_b(collection):
    if not collection:
        return False
    return len(collection) > 0


# =====================================================================
# SECTION 17: try-except blocks (for @i idiom dict t0)
# =====================================================================

def try_except_heavy():
    try:
        data = json.loads("{}")
        result = process_user_data(data)
    except (json.JSONDecodeError, TypeError) as e:
        logging.error(f"Parse error: {e}")
        result = None
    return result

def try_except_another():
    try:
        value = validate_input("test")
        output = transform_result(value)
    except ValueError as e:
        logging.error(f"Validation error: {e}")
        output = None
    return output


# =====================================================================
# SECTION 18: __eq__ + __hash__ pair (for @i idiom dict e0)
# =====================================================================

class ValueObject:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        if not isinstance(other, ValueObject):
            return False
        return self.value == other.value

    def __hash__(self):
        return hash(self.value)


# =====================================================================
# SECTION 19: Mixed code + complex expressions
# =====================================================================

def complex_expressions(data):
    # Nested ternary
    result = "positive" if data > 0 else "negative" if data < 0 else "zero"
    # Walrus operator
    processed = [y for x in data if (y := x * 2) > 10] if isinstance(data, list) else []
    # Chained comparisons
    in_range = 0 < data < 100 if isinstance(data, (int, float)) else False
    return result, processed, in_range


# =====================================================================
# SECTION 20: Large function with many identifiers (maximize @m savings)
# =====================================================================

class LargeServiceClass:
    def __init__(self, connection_pool_manager, max_retry_count, timeout_duration):
        self.connection_pool_manager = connection_pool_manager
        self.max_retry_count = max_retry_count
        self.timeout_duration = timeout_duration
        self.active_connection_list = []
        self.request_queue = []
        self.response_cache = {}
        self.error_count = 0
        self.total_request_count = 0

    def process_connection_request(self, request_data):
        self.total_request_count += 1
        if not self.active_connection_list:
            self.initialize_connection_pool()
        connection = self.active_connection_list.pop()
        try:
            response = self.send_request(connection, request_data)
            self.response_cache[request_data.get("id", "")] = response
            return response
        except Exception as e:
            self.error_count += 1
            logging.error(f"Request failed: {e}")
            return None
        finally:
            self.active_connection_list.append(connection)

    def initialize_connection_pool(self):
        for i in range(self.connection_pool_manager.max_connection_count):
            conn = self.connection_pool_manager.create_connection()
            self.active_connection_list.append(conn)

    def send_request(self, connection, request_data):
        return {"status": "ok", "data": request_data}

    def get_statistics(self):
        return {
            "total_requests": self.total_request_count,
            "errors": self.error_count,
            "cache_size": len(self.response_cache),
            "active_connections": len(self.active_connection_list),
        }

    def shutdown(self):
        for conn in self.active_connection_list:
            conn["status"] = "closed"
        self.active_connection_list.clear()
        self.response_cache.clear()
        self.request_queue.clear()
