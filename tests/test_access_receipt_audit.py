from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from medphys_agentbench.access_receipt_audit import audit_access_receipts, validate_probe_contract
from medphys_agentbench.route_qualification import RouteQualificationError, load_route_set

ROOT = Path(__file__).resolve().parents[1]


def _receipt_payload() -> dict[str, object]:
    path = next((ROOT / "receipts" / "access" / "groq-gpt-oss-20b-json-v2").glob("*.json"))
    return json.loads(path.read_text(encoding="utf-8"))


def test_repository_access_receipts_are_semantically_audited() -> None:
    route_sets = [load_route_set(path) for path in sorted((ROOT / "fleet").glob("*routes*.yaml"))]
    receipts = audit_access_receipts(route_sets)

    assert len(receipts) == 9
    assert len({receipt.payload["receipt_id"] for receipt in receipts}) == 9
    assert len({receipt.content_sha256 for receipt in receipts}) == 9
    assert any(receipt.payload["probe_version"] == "ollama-cloud-access-probe-v2" for receipt in receipts)


def test_probe_contract_rejects_unreviewed_versions_and_dependency_drift() -> None:
    payload = _receipt_payload()

    unknown = copy.deepcopy(payload)
    unknown["probe_version"] = "unreviewed-probe-v99"
    with pytest.raises(RouteQualificationError, match="unreviewed probe version"):
        validate_probe_contract(unknown)

    missing_dependency = copy.deepcopy(payload)
    missing_dependency["probe_dependencies"] = missing_dependency["probe_dependencies"][:-1]
    with pytest.raises(RouteQualificationError, match="dependency set"):
        validate_probe_contract(missing_dependency)

    duplicate_dependency = copy.deepcopy(payload)
    duplicate_dependency["probe_dependencies"].append(duplicate_dependency["probe_dependencies"][0])
    with pytest.raises(RouteQualificationError, match="unique objects"):
        validate_probe_contract(duplicate_dependency)
