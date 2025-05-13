# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

fastbencode is an implementation of the bencode serialization format originally used by BitTorrent. The package includes both a pure-Python version and an optional Rust extension based on PyO3. Both provide the same functionality, but the Rust extension provides significantly better performance.

## Development Commands

### Building and Installing

```bash
# Install in development mode with Rust extension
pip install -e .[rust]

# Install in development mode without Rust extension (pure Python)
pip install -e .

# Build the Rust extension
python -m pip install -e .[rust]
```

### Running Tests

```bash
# Run all tests (both Python and Rust implementations)
python -m unittest fastbencode.tests.test_suite

# Run specific test file
python -m unittest fastbencode.tests.test_bencode

# Run a specific test
python -m unittest fastbencode.tests.test_bencode.TestBencodeDecode.test_int
```

### Linting

```bash
# Run ruff linter
ruff check .
```

## Architecture

The codebase consists of two main implementations of the bencode format:

1. **Pure Python implementation** (`fastbencode/_bencode_py.py`):
   - Provides baseline functionality for all bencode operations
   - Used as a fallback when the Rust extension is not available

2. **Rust implementation** (`src/lib.rs`):
   - Implemented using PyO3 for Python bindings
   - Provides the same functionality with better performance
   - Compiled into `_bencode_rs` module

Both implementations provide the following key functions:
- `bencode`: Encode Python objects to bencode format
- `bdecode`: Decode bencode data to Python objects
- `bencode_utf8`: Like bencode but handles UTF-8 strings
- `bdecode_utf8`: Like bdecode but decodes strings as UTF-8
- `bdecode_as_tuple`: Like bdecode but returns tuples instead of lists

The main module (`fastbencode/__init__.py`) tries to import the Rust implementation first and falls back to the pure Python one if that fails.

## Testing Strategy

The test suite uses Python's unittest framework with a custom test multiplier that runs all tests against both the Python and Rust implementations. This ensures feature parity between the two implementations.

Tests are defined in `fastbencode/tests/test_bencode.py` and cover:
- Encoding and decoding basic types (integers, strings, lists, dictionaries)
- Error handling for malformed input
- Edge cases (large values, recursion limits, etc.)
- UTF-8 handling

## Codebase Specifics

- Dictionary keys in bencode must be bytestrings for performance reasons
- The `Bencached` class is used for pre-encoded values to avoid re-encoding
- Recursion depth is limited to prevent stack overflows (with special handling for different Python implementations)
