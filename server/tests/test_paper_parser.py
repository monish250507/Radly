"""
test_paper_parser.py — P2 hardened tests for paper_parser.py

Covers:
  - Section hierarchy, claim types, datasets, metrics, equations, figures, tables
  - Source-location assertions (startLine / line)
  - extraction_status and content_hash presence
  - Extraction failure contract: empty/None text → FAILED, not silent empty
  - PARTIAL status when no section headings found
"""
from server.engine.paper_parser import parse_paper_structure

FULL_PAPER = r"""
Abstract
We present a new model.

Introduction
The dataset used is CIFAR-10. We set learning rate to 1e-4. The model achieves 95.5% accuracy.
We conclude that it works.

Methodology
\begin{equation}
L = - \log P(x)
\end{equation}

\begin{figure}
\caption{Model Architecture}
\end{figure}

\begin{table}
\caption{Results Table}
\end{table}

$$ \alpha = 0.5 $$
"""

HEADINGLESS_TEXT = "This paper describes a new approach. Learning rate is 1e-4. Accuracy is 98%."


class TestSectionExtraction:
    def test_minimum_sections_extracted(self):
        ast = parse_paper_structure(FULL_PAPER)
        assert len(ast["sections"]) >= 3

    def test_section_ids_are_unique(self):
        ast = parse_paper_structure(FULL_PAPER)
        ids = [s["id"] for s in ast["sections"]]
        assert len(ids) == len(set(ids)), "Section IDs must be unique"

    def test_section_titles_nonempty(self):
        ast = parse_paper_structure(FULL_PAPER)
        for sec in ast["sections"]:
            assert sec.get("title", "").strip(), f"Section {sec.get('id')} has empty title"

    def test_section_start_line_populated(self):
        ast = parse_paper_structure(FULL_PAPER)
        for sec in ast["sections"]:
            assert isinstance(sec.get("startLine"), int), \
                f"Section {sec.get('id')} missing startLine"
            assert sec["startLine"] >= 1

    def test_section_text_nonempty(self):
        ast = parse_paper_structure(FULL_PAPER)
        for sec in ast["sections"]:
            assert sec.get("text", "").strip(), f"Section {sec.get('id')} has empty text"


class TestDatasetAndMetricExtraction:
    def test_dataset_detected(self):
        ast = parse_paper_structure(FULL_PAPER)
        assert len(ast["datasets"]) >= 1

    def test_dataset_name_correct(self):
        ast = parse_paper_structure(FULL_PAPER)
        names_lower = [d["name"].lower() for d in ast["datasets"]]
        assert any("cifar" in n for n in names_lower), \
            "CIFAR-10 should be detected as a dataset"

    def test_dataset_line_present(self):
        ast = parse_paper_structure(FULL_PAPER)
        for ds in ast["datasets"]:
            assert isinstance(ds.get("line"), int), \
                f"Dataset {ds['name']} missing line number"

    def test_metric_detected(self):
        ast = parse_paper_structure(FULL_PAPER)
        # "accuracy" should be in the text as a metric keyword
        metric_names = [m["name"].lower() for m in ast.get("metrics", [])]
        assert any("accuracy" in n for n in metric_names), \
            "Accuracy should be extracted as a metric"


class TestClaimExtraction:
    def test_minimum_claims_extracted(self):
        ast = parse_paper_structure(FULL_PAPER)
        assert len(ast["claims"]) >= 3

    def test_all_required_claim_types_present(self):
        ast = parse_paper_structure(FULL_PAPER)
        types = {c["type"] for c in ast["claims"]}
        assert "parameter_statement" in types, "Missing parameter_statement claims"
        assert "experimental_observation" in types, "Missing experimental_observation claims"
        assert "scientific_conclusion" in types, "Missing scientific_conclusion claims"

    def test_claims_have_line_numbers(self):
        ast = parse_paper_structure(FULL_PAPER)
        for claim in ast["claims"]:
            assert isinstance(claim.get("line"), int), \
                f"Claim missing line: {claim.get('text', '')[:50]}"


class TestEquationExtraction:
    def test_equations_count(self):
        ast = parse_paper_structure(FULL_PAPER)
        assert len(ast["equations"]) == 2, \
            f"Expected 2 equations (env + display), got {len(ast['equations'])}"

    def test_equation_variables_extracted(self):
        ast = parse_paper_structure(FULL_PAPER)
        vars_ = ast["equations"][0].get("variables", [])
        assert "L" in vars_, "Variable L not found in first equation"

    def test_equations_have_start_line(self):
        ast = parse_paper_structure(FULL_PAPER)
        for eq in ast["equations"]:
            assert isinstance(eq.get("startLine"), int), \
                f"Equation {eq.get('id')} missing startLine"


class TestFigureAndTableExtraction:
    def test_figure_detected(self):
        ast = parse_paper_structure(FULL_PAPER)
        assert len(ast["figures"]) == 1

    def test_figure_caption_extracted(self):
        ast = parse_paper_structure(FULL_PAPER)
        assert "Architecture" in ast["figures"][0]["caption"]

    def test_table_detected(self):
        ast = parse_paper_structure(FULL_PAPER)
        assert len(ast["tables"]) == 1

    def test_table_caption_extracted(self):
        ast = parse_paper_structure(FULL_PAPER)
        assert "Results" in ast["tables"][0]["caption"]


class TestNumericalClaims:
    def test_numerical_claims_extracted(self):
        ast = parse_paper_structure(FULL_PAPER)
        assert len(ast["numbers"]) >= 1

    def test_percentage_detected(self):
        ast = parse_paper_structure(FULL_PAPER)
        values = [n["value"] for n in ast["numbers"]]
        assert any("95" in v for v in values), \
            "95.5% should be detected as a numerical claim"


class TestExtractionStatusAndHash:
    def test_extraction_status_present(self):
        ast = parse_paper_structure(FULL_PAPER)
        assert "extraction_status" in ast
        assert ast["extraction_status"] in ("OK", "PARTIAL", "FAILED")

    def test_content_hash_present(self):
        ast = parse_paper_structure(FULL_PAPER)
        assert "content_hash" in ast
        assert len(ast["content_hash"]) == 16  # SHA1 truncated to 16 chars

    def test_content_hash_stable_across_identical_calls(self):
        ast1 = parse_paper_structure(FULL_PAPER)
        ast2 = parse_paper_structure(FULL_PAPER)
        assert ast1["content_hash"] == ast2["content_hash"]

    def test_content_hash_differs_for_different_content(self):
        ast1 = parse_paper_structure(FULL_PAPER)
        ast2 = parse_paper_structure(HEADINGLESS_TEXT)
        assert ast1["content_hash"] != ast2["content_hash"]


class TestExtractionFailureContract:
    def test_none_text_returns_failed_status(self):
        ast = parse_paper_structure(None)
        assert ast["extraction_status"] == "FAILED"

    def test_empty_string_returns_failed_status(self):
        ast = parse_paper_structure("")
        assert ast["extraction_status"] == "FAILED"

    def test_headingless_text_returns_partial_status(self):
        """Text with no recognizable headings → PARTIAL (not OK)."""
        ast = parse_paper_structure(HEADINGLESS_TEXT)
        assert ast["extraction_status"] == "PARTIAL", \
            "Headingless text should be PARTIAL, not OK"

    def test_headingless_text_has_fallback_section(self):
        """Headingless text gets a fallback 'Full Manuscript Body' section."""
        ast = parse_paper_structure(HEADINGLESS_TEXT)
        assert len(ast["sections"]) == 1
        assert "Manuscript" in ast["sections"][0]["title"] or "Body" in ast["sections"][0]["title"]
