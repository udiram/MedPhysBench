from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
import yaml

from medphys_agentbench.campaign import CampaignError, load_campaign
from medphys_agentbench.campaign_generation import (
    dump_campaign_yaml,
    generate_campaign_payload,
    write_campaign_manifest,
)
from medphys_agentbench.route_qualification import (
    ModelRoute,
    RouteQualificationError,
    load_access_probe_receipt,
    load_route_set,
    receipt_payload_with_hash,
    require_campaign_eligible_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
ROUTE_SET_PATH = ROOT / "fleet" / "model_routes_v1.yaml"
RELEASE_FILE = "releases/public_real_workflows_pilot_v0_6.yaml"


def _receipt_payload(route: ModelRoute, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "medphysbench.access-probe-receipt.v1",
        "receipt_id": f"probe-{route.route_id}-20260803t060100z",
        "route_id": route.route_id,
        "route_spec_sha256": route.route_spec_sha256,
        "route_set_id": "public-model-routes-v1",
        "fleet_id": "public-fleet-v1",
        "base_model_id": route.base_model_id,
        "adapter": route.adapter,
        "provider": route.provider,
        "model": route.model,
        "model_revision": route.model_revision,
        "probe_version": "access-probe-v1",
        "probe_implementation_path": "scripts/probes/test_access_probe.py",
        "probe_implementation_sha256": "b" * 64,
        "source_commit": "a" * 40,
        "started_at": "2026-08-03T06:45:00Z",
        "completed_at": "2026-08-03T06:46:00Z",
        "expires_at": "2026-08-03T12:45:00Z",
        "outcome": "available",
        "capabilities": {"observed": ["json_object"], "inferred": ["text"]},
        "quota": {"status": "sufficient", "source": "provider_headers"},
        "sanitized_metadata": {
            "endpoint_host": "api.groq.com",
            "http_status": 200,
            "served_model": route.model,
            "latency_ms": 42.0,
            "response_contract": "json_object",
        },
    }
    payload.update(overrides)
    return receipt_payload_with_hash(payload)


def _write_receipt(tmp_path: Path, route: ModelRoute, **overrides: object) -> Path:
    implementation = tmp_path / "scripts" / "probes" / "test_access_probe.py"
    implementation.parent.mkdir(parents=True, exist_ok=True)
    implementation.write_text("# reviewed test probe\n", encoding="utf-8")
    overrides.setdefault("probe_implementation_path", "scripts/probes/test_access_probe.py")
    overrides.setdefault("probe_implementation_sha256", sha256(implementation.read_bytes()).hexdigest())
    path = tmp_path / "receipts" / "access" / route.route_id / "probe.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_receipt_payload(route, **overrides), sort_keys=True), encoding="utf-8")
    return path


def test_committed_route_set_exposes_five_exact_groq_routes_without_claiming_access() -> None:
    route_set = load_route_set(ROUTE_SET_PATH)

    assert route_set.route_set_id == "public-model-routes-v1"
    assert len(route_set.routes) == 5
    assert {route.provider for route in route_set.routes} == {"groq"}
    assert {route.adapter for route in route_set.routes} == {"groq"}
    assert all(route.route_spec_sha256 for route in route_set.routes)
    assert all(route.revision_basis == "provider_alias" for route in route_set.routes)
    assert all(route.base_url == "https://api.groq.com/openai/v1" for route in route_set.routes)
    assert all(route.max_rate_limit_retries == 8 for route in route_set.routes)


def test_receipt_is_content_addressed_and_identity_bound(tmp_path: Path) -> None:
    route_set = load_route_set(ROUTE_SET_PATH)
    route = route_set.routes[0]
    path = _write_receipt(tmp_path, route)
    receipt = load_access_probe_receipt(path, route_set, repository_root=tmp_path)

    assert receipt.route_id == route.route_id
    assert receipt.outcome == "available"
    assert receipt.source_label.startswith("receipts/access/")

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["provider"] = "different-provider"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RouteQualificationError, match="content hash mismatch"):
        load_access_probe_receipt(path, route_set, repository_root=tmp_path)


def test_receipt_rejects_identity_drift_raw_bodies_and_excessive_lifetime(tmp_path: Path) -> None:
    route_set = load_route_set(ROUTE_SET_PATH)
    route = route_set.routes[0]

    identity_path = _write_receipt(tmp_path / "identity", route, provider="wrong")
    with pytest.raises(RouteQualificationError, match="identity mismatch"):
        load_access_probe_receipt(identity_path, route_set, repository_root=tmp_path / "identity")

    raw_path = _write_receipt(tmp_path / "raw", route, sanitized_metadata={"raw_body": "provider output"})
    with pytest.raises(RouteQualificationError, match="Invalid route/access contract"):
        load_access_probe_receipt(raw_path, route_set, repository_root=tmp_path / "raw")

    lifetime_path = _write_receipt(tmp_path / "lifetime", route, expires_at="2026-08-04T06:46:01Z")
    with pytest.raises(RouteQualificationError, match="lifetime exceeds"):
        load_access_probe_receipt(lifetime_path, route_set, repository_root=tmp_path / "lifetime")


def test_campaign_eligibility_fails_closed_for_expiry_future_and_quota(tmp_path: Path) -> None:
    route_set = load_route_set(ROUTE_SET_PATH)
    route = route_set.routes[0]
    receipt = load_access_probe_receipt(
        _write_receipt(tmp_path, route),
        route_set,
        repository_root=tmp_path,
    )

    with pytest.raises(RouteQualificationError, match="expired"):
        require_campaign_eligible_receipt(receipt, route, as_of=datetime(2026, 8, 3, 12, 45, 1, tzinfo=UTC))
    with pytest.raises(RouteQualificationError, match="future-dated"):
        require_campaign_eligible_receipt(receipt, route, as_of=datetime(2026, 8, 3, 6, 45, 30, tzinfo=UTC))

    unknown_path = _write_receipt(
        tmp_path / "unknown",
        route,
        quota={"status": "unknown", "source": "not_exposed"},
    )
    unknown = load_access_probe_receipt(unknown_path, route_set, repository_root=tmp_path / "unknown")
    with pytest.raises(RouteQualificationError, match="explicit recorded override"):
        require_campaign_eligible_receipt(
            unknown,
            route,
            as_of=datetime(2026, 8, 3, 7, tzinfo=UTC),
        )
    require_campaign_eligible_receipt(
        unknown,
        route,
        as_of=datetime(2026, 8, 3, 7, tzinfo=UTC),
        allow_unknown_quota=True,
    )


def test_available_receipt_must_postdate_route_freeze_and_prove_response_contract(tmp_path: Path) -> None:
    route_set = load_route_set(ROUTE_SET_PATH)
    route = route_set.routes[0]

    prefreeze_path = _write_receipt(
        tmp_path / "prefreeze",
        route,
        started_at="2026-08-03T06:10:00Z",
        completed_at="2026-08-03T06:20:00Z",
        expires_at="2026-08-03T12:20:00Z",
    )
    with pytest.raises(RouteQualificationError, match="predates the frozen route set"):
        load_access_probe_receipt(prefreeze_path, route_set, repository_root=tmp_path / "prefreeze")

    wrong_contract_path = _write_receipt(
        tmp_path / "contract",
        route,
        capabilities={"observed": ["text"], "inferred": []},
        sanitized_metadata={
            "endpoint_host": "api.groq.com",
            "http_status": 200,
            "response_contract": "text",
        },
    )
    with pytest.raises(RouteQualificationError, match="does not prove route response contract"):
        load_access_probe_receipt(wrong_contract_path, route_set, repository_root=tmp_path / "contract")


def test_receipt_binds_reviewed_probe_implementation_bytes(tmp_path: Path) -> None:
    route_set = load_route_set(ROUTE_SET_PATH)
    route = route_set.routes[0]
    path = _write_receipt(tmp_path, route)
    implementation = tmp_path / "scripts" / "probes" / "test_access_probe.py"
    implementation.write_text("# modified after receipt\n", encoding="utf-8")

    with pytest.raises(RouteQualificationError, match="implementation hash mismatch"):
        load_access_probe_receipt(path, route_set, repository_root=tmp_path)


def test_campaign_generation_is_deterministic_and_does_not_create_run_state(tmp_path: Path) -> None:
    route_set = load_route_set(ROUTE_SET_PATH)
    routes = [route_set.routes[0], route_set.routes[1]]
    receipts = {
        route.route_id: load_access_probe_receipt(
            _write_receipt(tmp_path, route),
            route_set,
            repository_root=tmp_path,
        )
        for route in routes
    }
    kwargs = {
        "release_file": RELEASE_FILE,
        "campaign_id": "generated-groq-proof-v2",
        "results_dir": "runs/generated-groq-proof-v2",
        "as_of": datetime(2026, 8, 3, 7, tzinfo=UTC),
    }

    first = generate_campaign_payload(
        route_set,
        receipts,
        route_ids=[routes[1].route_id, routes[0].route_id],
        **kwargs,
    )
    second = generate_campaign_payload(
        route_set,
        dict(reversed(list(receipts.items()))),
        route_ids=[routes[0].route_id, routes[1].route_id],
        **kwargs,
    )

    assert dump_campaign_yaml(first) == dump_campaign_yaml(second)
    assert first["schema_version"] == "medeval.campaign.v2"
    assert [model["route_id"] for model in first["models"]] == sorted(receipts)
    assert all(model["access_receipt_sha256"] for model in first["models"])
    assert not (tmp_path / "runs").exists()

    output = tmp_path / "campaigns" / "generated.yaml"
    assert write_campaign_manifest(output, first) is True
    assert write_campaign_manifest(output, first) is False
    with pytest.raises(RouteQualificationError, match="Refusing to overwrite"):
        write_campaign_manifest(output, {**first, "campaign_id": "different-campaign-v2"})


def test_v2_campaign_load_revalidates_route_receipt_and_release_bindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from medphys_agentbench import campaign as campaign_module
    from medphys_agentbench import release_loader as release_loader_module

    task_source = ROOT / "tasks" / "dev" / "physics_units_001" / "task.yaml"
    task_target = tmp_path / "tasks" / "dev" / "physics_units_001" / "task.yaml"
    task_target.parent.mkdir(parents=True)
    shutil.copy2(task_source, task_target)

    release_path = tmp_path / "releases" / "route_test.yaml"
    release_path.parent.mkdir(parents=True)
    release_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "medeval.release.v1",
                "release_id": "route-test-v1",
                "title": "Route test",
                "description": "One-task evidence-binding fixture.",
                "task_files": ["../tasks/dev/physics_units_001/task.yaml"],
                "expected_attempts_per_task": 1,
                "integrity_profile": "development",
                "max_family_share": 1.0,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    original_routes = yaml.safe_load(ROUTE_SET_PATH.read_text(encoding="utf-8"))
    original_route = original_routes["routes"][0]
    fleet_path = tmp_path / "fleet" / "public_fleet_v1.yaml"
    fleet_path.parent.mkdir(parents=True)
    fleet_path.write_text(
        yaml.safe_dump(
            {
                "fleet_id": "public-fleet-v1",
                "models": [
                    {
                        "base_model_id": original_route["base_model_id"],
                        "planned_routes": ["groq"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    route_path = tmp_path / "fleet" / "model_routes_v1.yaml"
    route_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "medphysbench.model-routes.v1",
                "route_set_id": "route-test-set-v1",
                "fleet_file": "fleet/public_fleet_v1.yaml",
                "fleet_id": "public-fleet-v1",
                "frozen_at": "2026-08-03T06:00:00Z",
                "routes": [original_route],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    route_set = load_route_set(route_path, repository_root=tmp_path)
    route = route_set.routes[0]
    receipt_path = _write_receipt(tmp_path, route, route_set_id=route_set.route_set_id)
    receipt = load_access_probe_receipt(receipt_path, route_set, repository_root=tmp_path)

    monkeypatch.setattr(release_loader_module, "REPOSITORY_TASKS_ROOT", (tmp_path / "tasks").resolve())
    payload = generate_campaign_payload(
        route_set,
        {route.route_id: receipt},
        route_ids=[route.route_id],
        release_file="releases/route_test.yaml",
        campaign_id="route-test-campaign-v2",
        results_dir="runs/route-test-campaign-v2",
        as_of=datetime(2026, 8, 3, 7, tzinfo=UTC),
        repository_root=tmp_path,
    )
    campaign_path = tmp_path / "campaigns" / "route_test.yaml"
    write_campaign_manifest(campaign_path, payload)

    monkeypatch.setattr(campaign_module, "REPOSITORY_ROOT", tmp_path.resolve())
    campaign = load_campaign(campaign_path)
    assert campaign.schema_version == "medeval.campaign.v2"
    assert campaign.route_set_id == "route-test-set-v1"
    assert campaign.models[0].access_receipt_sha256 == receipt.content_sha256

    changed = dict(receipt.payload)
    changed["sanitized_metadata"] = {**changed["sanitized_metadata"], "latency_ms": 43.0}
    changed.pop("content_sha256")
    receipt_path.write_text(json.dumps(receipt_payload_with_hash(changed)), encoding="utf-8")
    with pytest.raises(CampaignError, match="Access receipt hash mismatch"):
        load_campaign(campaign_path)
