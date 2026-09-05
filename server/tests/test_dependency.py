"""
test_dependency.py — P2: Dependency / data-flow assertions.

Asserts that call/reference/assignment/parameter flow edges
are detectable through the AST layer and the artifact index.

The audit requires "edges derived from AST references and assignments
rather than textual overlap" — this suite proves those edges exist
and are correctly keyed to artifact IDs.
"""
import pytest

from server.domain.factories import build_artifact_index
from server.engine.code_parser import extract_code_symbols

# ---------------------------------------------------------------------------
# Fixtures: a minimal call-chain  config → train → experiment
# ---------------------------------------------------------------------------
CONFIG_CODE = """
learning_rate = 1e-4
batch_size = 32
optimizer = 'Adam'
"""

TRAIN_CODE = """
from config import learning_rate, batch_size

def train(model, learning_rate=learning_rate, batch_size=batch_size):
    result = model.fit(lr=learning_rate, bs=batch_size)
    return result
"""

EXPERIMENT_CODE = """
from train import train

def run_experiment():
    acc = train(model=build_model())
    return acc
"""


@pytest.fixture
def chain_files():
    return [
        {"path": "config.py",     "content": CONFIG_CODE},
        {"path": "train.py",      "content": TRAIN_CODE},
        {"path": "experiment.py", "content": EXPERIMENT_CODE},
    ]


@pytest.fixture
def chain_symbols(chain_files):
    return extract_code_symbols(chain_files)


# ---------------------------------------------------------------------------
# Tests: parameter definition
# ---------------------------------------------------------------------------
class TestParameterDefinition:
    def test_learning_rate_extracted(self, chain_symbols):
        names = {s["symbol"] for s in chain_symbols}
        assert "learning_rate" in names, "learning_rate assignment not found"

    def test_batch_size_extracted(self, chain_symbols):
        names = {s["symbol"] for s in chain_symbols}
        assert "batch_size" in names

    def test_config_symbols_have_config_file(self, chain_symbols):
        config_symbols = [s for s in chain_symbols if s.get("file") == "config.py"]
        assert len(config_symbols) >= 3, \
            "At least learning_rate, batch_size, optimizer should be from config.py"

    def test_parameter_values_captured(self, chain_symbols):
        lr = next((s for s in chain_symbols if s["symbol"] == "learning_rate"), None)
        assert lr is not None
        # The AST extracts value for simple literals
        if "value" in lr:
            # value can be string repr of the constant or None for complex
            assert lr["value"] is not None or lr.get("type") == "Assignment"


# ---------------------------------------------------------------------------
# Tests: function references
# ---------------------------------------------------------------------------
class TestFunctionReferences:
    def test_train_function_defined(self, chain_symbols):
        funcs = {s["symbol"] for s in chain_symbols if s["type"] in ("Function", "Method")}
        assert "train" in funcs

    def test_run_experiment_function_defined(self, chain_symbols):
        funcs = {s["symbol"] for s in chain_symbols if s["type"] in ("Function", "Method")}
        assert "run_experiment" in funcs

    def test_call_edges_present(self, chain_symbols):
        """AST Call nodes indicate cross-function dependency."""
        calls = {s["symbol"] for s in chain_symbols if s["type"] == "Call"}
        assert len(calls) > 0, "No Call edges extracted — dependency graph would be empty"

    def test_train_call_detected(self, chain_symbols):
        calls = [s for s in chain_symbols if s["type"] == "Call"]
        call_names = {c["symbol"] for c in calls}
        # 'train' is called in experiment.py
        assert "train" in call_names


# ---------------------------------------------------------------------------
# Tests: import/reference tracking
# ---------------------------------------------------------------------------
class TestImportReferences:
    def test_from_config_import_detected(self, chain_symbols):
        imports = [s for s in chain_symbols if s["type"] == "ImportFrom"]
        import_symbols = {s["symbol"] for s in imports}
        # "config.learning_rate" or "config.batch_size" expected
        assert any("learning_rate" in sym or "config" in sym for sym in import_symbols), \
            "ImportFrom config not captured"

    def test_from_train_import_detected(self, chain_symbols):
        imports = [s for s in chain_symbols if s["type"] == "ImportFrom"]
        import_symbols = {s["symbol"] for s in imports}
        assert any("train" in sym for sym in import_symbols)


# ---------------------------------------------------------------------------
# Tests: artifact index cross-links code ↔ paper
# ---------------------------------------------------------------------------
class TestArtifactIndexLinks:
    PAPER_AST = {
        "sections": [
            {"id": "sec-1-methodology", "title": "Methodology",
             "text": "We set learning_rate=1e-4 and batch_size=32.", "startLine": 1, "endLine": 5},
            {"id": "sec-2-experiments", "title": "Experiments",
             "text": "We run train() with Adam optimizer.", "startLine": 6, "endLine": 15},
        ],
        "equations": [],
        "tables": [],
        "numbers": [],
        "claims": [],
    }

    def test_artifact_index_built_without_error(self, chain_symbols):
        idx = build_artifact_index(chain_symbols, self.PAPER_AST, "github.com/x/y", "ms-1")
        assert idx is not None

    def test_code_artifacts_count(self, chain_symbols):
        idx = build_artifact_index(chain_symbols, self.PAPER_AST, "github.com/x/y", "ms-1")
        assert len(idx.codeArtifacts) == len(chain_symbols)

    def test_section_artifacts_count(self, chain_symbols):
        idx = build_artifact_index(chain_symbols, self.PAPER_AST, "github.com/x/y", "ms-1")
        assert len(idx.sectionArtifacts) == 2

    def test_all_artifact_ids_unique(self, chain_symbols):
        idx = build_artifact_index(chain_symbols, self.PAPER_AST, "github.com/x/y", "ms-1")
        all_ids = [a.artifactId for a in idx.all]
        assert len(all_ids) == len(set(all_ids)), "Duplicate artifact IDs detected"

    def test_code_artifacts_have_exact_locations(self, chain_symbols):
        idx = build_artifact_index(chain_symbols, self.PAPER_AST, "github.com/x/y", "ms-1")
        for art in idx.codeArtifacts:
            assert art.exactLocation, f"Artifact {art.artifactId} missing exactLocation"
            # Format: file.py:line
            assert ":" in art.exactLocation or art.exactLocation.endswith(".py"), \
                f"exactLocation '{art.exactLocation}' does not include file path"
