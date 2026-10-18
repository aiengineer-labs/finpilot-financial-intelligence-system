import json
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = API_ROOT.parents[1]
EVIDENCE = API_ROOT / "app" / "evidence" / "model_redteam.json"


def test_model_redteam_evidence_matches_its_committed_report() -> None:
    """The governance gate reads a bundled copy; it must agree with the report it came from."""

    if not EVIDENCE.exists():
        pytest.skip("the model red team has not been recorded")
    evidence = json.loads(EVIDENCE.read_text())
    report = json.loads((REPO_ROOT / evidence["report"]).read_text())
    for key, value in evidence["metrics"].items():
        assert report["result"][key] == value, key
    assert evidence["duration_ms"] == report["result"]["duration_ms"]
    assert len(evidence["findings"]) <= len(report["failures"])
