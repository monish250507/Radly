"""
test_security.py — P2: Security tests.

Validates that ingestion limits, payload size guards, and malicious inputs
are handled gracefully without crashing or RCE.
"""
import pytest
from fastapi.testclient import TestClient

from server.engine.paper_parser import MAX_INPUT_BYTES, extract_text_from_document
from server.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# API Level Security
# ---------------------------------------------------------------------------
def test_oversized_request_rejected():
    """Requests over 10MB should be rejected by middleware."""
    # Create a payload slightly larger than 10MB
    large_string = "A" * (10 * 1024 * 1024 + 100)
    response = client.post(
        "/api/parse-paper",
        json={"paperText": large_string},
        headers={"Content-Length": str(len(large_string) + 50)}
    )
    assert response.status_code == 413
    assert "too large" in response.json().get("error", "").lower()

def test_rate_limiting():
    """Rapid requests should trigger 429."""
    # The limit is 30 write requests per minute
    # We simulate 35 rapid requests
    responses = []
    for _ in range(35):
        resp = client.post("/api/parse-paper", json={"paperText": "test"})
        responses.append(resp.status_code)
    
    assert 429 in responses, "Rate limiter did not trigger under load"

# ---------------------------------------------------------------------------
# Parser Level Security
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_oversized_paper_truncation():
    """If an oversized document sneaks through, the parser should truncate it, not crash."""
    large_bytes = b"X" * (MAX_INPUT_BYTES + 1000)
    
    # Should not raise exception, should truncate and return text
    text = await extract_text_from_document(large_bytes, file_type="txt")
    assert len(text.encode('utf-8')) <= MAX_INPUT_BYTES

@pytest.mark.asyncio
async def test_malicious_pdf_payload():
    """A completely invalid binary payload should fail gracefully."""
    malicious_bytes = b"%PDF-1.4 \x00\x00\x00\x00\xff\xff"
    
    with pytest.raises(ValueError) as exc:
        await extract_text_from_document(malicious_bytes, file_type="pdf")
    
    assert "failed" in str(exc.value).lower()
