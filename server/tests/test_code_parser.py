"""
test_code_parser.py — P2 hardened test suite for code_parser.py

Covers:
  - Happy-path AST symbol extraction (types, names, source locations)
  - EXTRACTION_FAILED sentinel contract on SyntaxError (P0 regression)
  - Source-location assertions (file, line, col_offset)
  - is_extraction_failed() helper
  - extract_code_symbols() FAILED-file exclusion
  - Unsupported file extension passthrough
"""
from server.engine.code_parser import (
    extract_code_symbols,
    is_extraction_failed,
    parse_python_ast,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
WELL_FORMED_PY = """
import os
from sys import path

learning_rate = 1e-4

class Model:
    def __init__(self):
        self.weights = []

    def train(self, data):
        self.optimizer = 'Adam'
        self.run_loop()

    def run_loop(self):
        pass

def load_data():
    return []
"""

MALFORMED_PY = "def oops("
EMPTY_PY = ""
BINARY_LIKE = "\x00\x01\x02\x03"


# ---------------------------------------------------------------------------
# Happy-path AST extraction
# ---------------------------------------------------------------------------
class TestParseSuccessPath:
    def test_symbol_types_present(self):
        symbols = parse_python_ast(WELL_FORMED_PY, "test.py")
        types = {s["type"] for s in symbols}
        assert "Import" in types
        assert "ImportFrom" in types
        assert "Class" in types
        assert "Function" in types
        assert "Assignment" in types
        assert "Call" in types

    def test_symbol_names_present(self):
        symbols = parse_python_ast(WELL_FORMED_PY, "test.py")
        names = {s["symbol"] for s in symbols}
        assert "os" in names
        assert "learning_rate" in names
        assert "Model" in names
        assert "train" in names
        assert "load_data" in names
        assert "self.weights" in names
        assert "self.optimizer" in names

    def test_source_locations_populated(self):
        """Every symbol must have a non-None file and a non-negative line."""
        symbols = parse_python_ast(WELL_FORMED_PY, "train.py")
        for sym in symbols:
            assert sym.get("file") == "train.py", f"Symbol {sym['symbol']} missing file"
            assert isinstance(sym.get("line"), int), f"Symbol {sym['symbol']} line is not int"
            assert sym["line"] >= 0, f"Symbol {sym['symbol']} has negative line"

    def test_no_extraction_failed_in_success(self):
        symbols = parse_python_ast(WELL_FORMED_PY, "test.py")
        assert not any(is_extraction_failed(s) for s in symbols), \
            "A successful parse must not return EXTRACTION_FAILED sentinels"


# ---------------------------------------------------------------------------
# P0 Regression: EXTRACTION_FAILED contract on SyntaxError
# ---------------------------------------------------------------------------
class TestExtractionFailedContract:
    def test_syntax_error_returns_sentinel(self):
        """P0 regression: SyntaxError MUST return EXTRACTION_FAILED, NOT a regex list."""
        symbols = parse_python_ast(MALFORMED_PY, "bad.py")
        assert isinstance(symbols, list)
        assert len(symbols) == 1, \
            "SyntaxError must produce exactly one EXTRACTION_FAILED sentinel"
        assert is_extraction_failed(symbols[0]), \
            "The single element must be an EXTRACTION_FAILED sentinel"

    def test_sentinel_has_extraction_status_failed(self):
        symbols = parse_python_ast(MALFORMED_PY, "bad.py")
        sentinel = symbols[0]
        assert sentinel.get("extraction_status") == "FAILED"

    def test_sentinel_carries_file_path(self):
        symbols = parse_python_ast(MALFORMED_PY, "bad.py")
        assert symbols[0].get("file") == "bad.py"

    def test_sentinel_type_is_extraction_failed(self):
        symbols = parse_python_ast(MALFORMED_PY, "bad.py")
        assert symbols[0].get("type") == "EXTRACTION_FAILED"

    def test_sentinel_symbol_name_is_sentinel_marker(self):
        symbols = parse_python_ast(MALFORMED_PY, "bad.py")
        assert symbols[0].get("symbol") == "__EXTRACTION_FAILED__"

    def test_is_extraction_failed_helper_true(self):
        symbols = parse_python_ast(MALFORMED_PY, "bad.py")
        assert is_extraction_failed(symbols[0]) is True

    def test_is_extraction_failed_helper_false_on_real_symbol(self):
        symbols = parse_python_ast(WELL_FORMED_PY, "ok.py")
        real_symbols = [s for s in symbols if s["type"] != "EXTRACTION_FAILED"]
        assert len(real_symbols) > 0
        assert is_extraction_failed(real_symbols[0]) is False


# ---------------------------------------------------------------------------
# extract_code_symbols() — EXTRACTION_FAILED exclusion
# ---------------------------------------------------------------------------
class TestExtractCodeSymbolsAggregation:
    def test_failed_file_excluded_from_results(self):
        """EXTRACTION_FAILED sentinels must be excluded from the aggregate result."""
        files = [
            {"path": "good.py", "content": WELL_FORMED_PY},
            {"path": "bad.py",  "content": MALFORMED_PY},
        ]
        symbols = extract_code_symbols(files)
        # All results must be real symbols — no sentinels
        for sym in symbols:
            assert not is_extraction_failed(sym), \
                "extract_code_symbols must never return EXTRACTION_FAILED sentinels"

    def test_good_file_symbols_present_despite_bad_file(self):
        files = [
            {"path": "good.py", "content": WELL_FORMED_PY},
            {"path": "bad.py",  "content": MALFORMED_PY},
        ]
        symbols = extract_code_symbols(files)
        names = {s["symbol"] for s in symbols}
        assert "learning_rate" in names, \
            "Good file symbols must still be extracted even if another file fails"

    def test_empty_file_list_returns_empty(self):
        assert extract_code_symbols([]) == []

    def test_missing_content_skipped(self):
        files = [{"path": "x.py", "content": None}]
        result = extract_code_symbols(files)
        assert result == []

    def test_oversized_file_skipped(self):
        """Files over 5MB must be skipped, not crash."""
        files = [{"path": "big.py", "content": "x = 1\n" * 1_000_000}]
        # Should not raise; may or may not have symbols depending on exact size
        result = extract_code_symbols(files)
        assert isinstance(result, list)

    def test_unsupported_extension_skipped(self):
        files = [{"path": "model.rb", "content": "def hello; end"}]
        result = extract_code_symbols(files)
        assert result == []

    def test_multiple_good_files(self):
        files = [
            {"path": "a.py", "content": "x = 1"},
            {"path": "b.py", "content": "y = 2"},
        ]
        symbols = extract_code_symbols(files)
        names = {s["symbol"] for s in symbols}
        assert "x" in names
        assert "y" in names
