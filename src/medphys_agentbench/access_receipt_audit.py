"""Repository-wide audit for immutable, non-scoring access-probe receipts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .route_qualification import AccessProbeReceipt, RouteQualificationError, RouteSet, load_access_probe_receipt

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ProbeContract:
    implementation_path: str
    dependency_paths: frozenset[str]


PROBE_CONTRACTS = {
    "openai-access-probe-v1": ProbeContract(
        implementation_path="scripts/probes/openai_access_probe.py",
        dependency_paths=frozenset(),
    ),
    "openai-access-probe-v2": ProbeContract(
        implementation_path="scripts/probes/openai_access_probe_v2.py",
        dependency_paths=frozenset(
            {
                "scripts/probes/openai_access_probe.py",
                "src/medphys_agentbench/adapters/openai_compatible.py",
                "src/medphys_agentbench/json_utils.py",
                "src/medphys_agentbench/route_qualification.py",
            }
        ),
    ),
    "openai-access-probe-v3": ProbeContract(
        implementation_path="scripts/probes/openai_access_probe_v3.py",
        dependency_paths=frozenset(
            {
                "scripts/probes/openai_access_probe.py",
                "src/medphys_agentbench/adapters/openai_compatible.py",
                "src/medphys_agentbench/json_utils.py",
                "src/medphys_agentbench/route_qualification.py",
            }
        ),
    ),
    "ollama-access-probe-v1": ProbeContract(
        implementation_path="scripts/probes/ollama_access_probe.py",
        dependency_paths=frozenset(
            {
                "src/medphys_agentbench/adapters/ollama.py",
                "src/medphys_agentbench/json_utils.py",
                "src/medphys_agentbench/route_qualification.py",
            }
        ),
    ),
    "ollama-cloud-access-probe-v2": ProbeContract(
        implementation_path="scripts/probes/ollama_cloud_access_probe_v2.py",
        dependency_paths=frozenset(
            {
                "scripts/probes/ollama_access_probe.py",
                "src/medphys_agentbench/adapters/ollama.py",
                "src/medphys_agentbench/json_utils.py",
                "src/medphys_agentbench/route_qualification.py",
            }
        ),
    ),
}


def validate_probe_contract(payload: dict[str, Any]) -> None:
    """Fail closed when a receipt uses an unreviewed probe or dependency set."""
    version = str(payload.get("probe_version", ""))
    contract = PROBE_CONTRACTS.get(version)
    if contract is None:
        raise RouteQualificationError(f"Access receipt uses unreviewed probe version {version!r}.")
    if payload.get("probe_implementation_path") != contract.implementation_path:
        raise RouteQualificationError(f"Access receipt probe path does not match {version!r}.")
    dependencies = payload.get("probe_dependencies", [])
    if not isinstance(dependencies, list):
        raise RouteQualificationError("Access receipt probe_dependencies must be a list.")
    paths = [str(item.get("path", "")) for item in dependencies if isinstance(item, dict)]
    if len(paths) != len(dependencies) or len(paths) != len(set(paths)):
        raise RouteQualificationError("Access receipt probe dependency paths must be unique objects.")
    if frozenset(paths) != contract.dependency_paths:
        raise RouteQualificationError(f"Access receipt dependency set does not match {version!r}.")


def audit_access_receipts(
    route_sets: list[RouteSet],
    *,
    repository_root: Path = REPOSITORY_ROOT,
) -> list[AccessProbeReceipt]:
    """Validate every committed receipt and its unique route/source/probe bindings."""
    root = repository_root.resolve()
    route_index: dict[str, RouteSet] = {}
    for route_set in route_sets:
        for route in route_set.routes:
            if route.route_id in route_index:
                raise RouteQualificationError(f"Duplicate route ID while auditing receipts: {route.route_id!r}.")
            route_index[route.route_id] = route_set

    receipt_root = root / "receipts" / "access"
    paths = sorted(receipt_root.rglob("*.json")) if receipt_root.is_dir() else []
    receipts: list[AccessProbeReceipt] = []
    receipt_ids: set[str] = set()
    content_hashes: set[str] = set()
    for path in paths:
        relative_parts = path.relative_to(receipt_root).parts
        if len(relative_parts) != 2:
            raise RouteQualificationError(f"Access receipt must be stored as <route-id>/<file>.json: {path}.")
        route_id = relative_parts[0]
        route_set = route_index.get(route_id)
        if route_set is None:
            raise RouteQualificationError(f"Access receipt directory references unknown route {route_id!r}.")
        receipt = load_access_probe_receipt(path, route_set, repository_root=root)
        if receipt.route_id != route_id:
            raise RouteQualificationError(f"Access receipt is stored under the wrong route directory: {path}.")
        validate_probe_contract(receipt.payload)
        receipt_id = str(receipt.payload["receipt_id"])
        if receipt_id in receipt_ids:
            raise RouteQualificationError(f"Duplicate access receipt ID {receipt_id!r}.")
        if receipt.content_sha256 in content_hashes:
            raise RouteQualificationError(f"Duplicate access receipt content hash {receipt.content_sha256!r}.")
        receipt_ids.add(receipt_id)
        content_hashes.add(receipt.content_sha256)
        receipts.append(receipt)
    return receipts


def validate_access_entry_receipt(
    entry: dict[str, Any],
    receipts_by_path: Mapping[str, AccessProbeReceipt],
) -> None:
    """Bind an optional public access-ledger claim to one audited receipt."""
    reference = entry.get("access_probe_receipt")
    if reference is None:
        return
    if not isinstance(reference, dict):
        raise RouteQualificationError("access_probe_receipt must be an object.")
    path = str(reference.get("path", ""))
    receipt = receipts_by_path.get(path)
    if receipt is None:
        raise RouteQualificationError(f"Access ledger references an unaudited receipt {path!r}.")
    if reference.get("sha256") != receipt.content_sha256:
        raise RouteQualificationError(f"Access ledger receipt hash mismatch for {path!r}.")
    expected_identity = {
        "provider": receipt.payload["provider"],
        "model": receipt.payload["model"],
        "base_model_id": receipt.payload["base_model_id"],
    }
    mismatches = [key for key, value in expected_identity.items() if entry.get(key) != value]
    if mismatches:
        raise RouteQualificationError(
            f"Access ledger receipt identity mismatch for {path!r}: {', '.join(sorted(mismatches))}."
        )
    status = entry.get("status")
    if status == "available" and receipt.outcome != "available":
        raise RouteQualificationError("Available access status must reference an available receipt.")
    if status == "blocked" and receipt.outcome == "available":
        raise RouteQualificationError("Blocked access status must reference a non-available receipt.")
