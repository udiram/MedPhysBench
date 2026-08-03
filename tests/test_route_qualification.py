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
LOCAL_OLLAMA_ROUTE_SET_PATH = ROOT / "fleet" / "local_ollama_routes_v1.yaml"
LOCAL_OLLAMA_CANDIDATE_ROUTE_SET_PATH = ROOT / "fleet" / "local_ollama_candidate_routes_v1.yaml"
LOCAL_OLLAMA_CANDIDATE_V2_ROUTE_SET_PATH = ROOT / "fleet" / "local_ollama_candidate_routes_v2.yaml"
PROVIDER_ROUTE_SET_PATH = ROOT / "fleet" / "provider_expansion_routes_v2.yaml"
GROQ_REASONING_ROUTE_SET_PATH = ROOT / "fleet" / "groq_reasoning_routes_v2.yaml"
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


def _write_ollama_receipt(tmp_path: Path, route: ModelRoute, **overrides: object) -> Path:
    implementation = tmp_path / "scripts" / "probes" / "ollama_access_probe.py"
    implementation.parent.mkdir(parents=True, exist_ok=True)
    implementation.write_text("# reviewed ollama probe\n", encoding="utf-8")
    dependencies = (
        "src/medphys_agentbench/adapters/ollama.py",
        "src/medphys_agentbench/json_utils.py",
        "src/medphys_agentbench/route_qualification.py",
    )
    for label in dependencies:
        dependency = tmp_path / label
        dependency.parent.mkdir(parents=True, exist_ok=True)
        dependency.write_text(f"# {label}\n", encoding="utf-8")
    payload = receipt_payload_with_hash(
        {
            "schema_version": "medphysbench.access-probe-receipt.v1",
            "receipt_id": f"probe-{route.route_id}-20260803t123100z",
            "route_id": route.route_id,
            "route_spec_sha256": route.route_spec_sha256,
            "route_set_id": "local-ollama-routes-v1",
            "fleet_id": "public-fleet-v1",
            "base_model_id": route.base_model_id,
            "adapter": route.adapter,
            "provider": route.provider,
            "model": route.model,
            "model_revision": route.model_revision,
            "probe_version": "ollama-access-probe-v1",
            "probe_implementation_path": "scripts/probes/ollama_access_probe.py",
            "probe_implementation_sha256": sha256(implementation.read_bytes()).hexdigest(),
            "probe_dependencies": [
                {"path": label, "content_sha256": sha256((tmp_path / label).read_bytes()).hexdigest()}
                for label in dependencies
            ],
            "source_commit": "a" * 40,
            "started_at": "2026-08-03T12:31:00Z",
            "completed_at": "2026-08-03T12:31:01Z",
            "expires_at": "2026-08-03T18:31:01Z",
            "outcome": "available",
            "capabilities": {
                "observed": ["image", "json_schema", "strict_schema", "text"],
                "inferred": list(route.modalities),
            },
            "quota": {"status": "sufficient", "source": "local_runtime"},
            "sanitized_metadata": {
                "endpoint_host": "127.0.0.1",
                "http_status": 200,
                "served_model": route.model,
                "served_revision": (
                    route.model_revision
                    if str(route.model_revision).startswith("sha256:")
                    else f"sha256:{route.model_revision}"
                ),
                "latency_ms": 42.0,
                "response_contract": "json_schema",
            },
            **overrides,
        }
    )
    path = tmp_path / "receipts" / "access" / route.route_id / "probe.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
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
    assert {route.route_id: route.route_spec_sha256 for route in route_set.routes} == {
        "groq-gpt-oss-120b": "c2a1159795627f6c068ae82e57fb5ed12d74a2d383980868a6f79ce58d14cca1",
        "groq-gpt-oss-20b": "1b62334037eed3fa846ef69feb269d913340555f9e6f683607e0d635b068557f",
        "groq-llama-3.1-8b-instant": "9aa9a499f94007cfc61da05eb8f9b53800a870876b6e9bb1325b3e8ce5c14b5f",
        "groq-llama-3.3-70b-versatile": "d65ee2f69cbd36f44a13cf08d7d8a5f93052a24705495ebe08280f58eecfb92d",
        "groq-qwen-3.6-27b": "95e16daa78ba0f10594a6d0d60a6f440a4d43de32a7217fb6090bbfb957660c5",
    }
    assert all(route.send_temperature is True for route in route_set.routes)
    assert all(route.send_seed is True for route in route_set.routes)
    assert all(route.completion_limit_field == "max_completion_tokens" for route in route_set.routes)
    assert all(route.response_format_dialect == "openai" for route in route_set.routes)
    assert all(route.send_reasoning_effort is True for route in route_set.routes)


def test_provider_expansion_routes_are_frozen_but_do_not_claim_access() -> None:
    route_set = load_route_set(PROVIDER_ROUTE_SET_PATH)

    assert route_set.route_set_id == "provider-expansion-routes-v2"
    assert len(route_set.routes) == 7
    assert {route.provider for route in route_set.routes} == {"google", "cohere"}
    assert {route.route_id: route.route_spec_sha256 for route in route_set.routes} == {
        "cohere-command-a-plus-05-2026": "cd305e9b740ebd69e62b63b0939e6956a00c43f0f6062d7dfeb2aa1f7046e2d9",
        "google-gemini-2.5-flash": "8220597b372b51d5768686d77f0f9352a8727b7addd9683b957425b303b7abca",
        "google-gemini-2.5-pro": "580a093869c12d0746c3e710f14eac165c9ebf4ca201819437092f8b544a1cb3",
        "google-gemini-3.1-flash-lite": "f25ccb7e39c2ffd65256910395601b3350933f64dd173aa4dc61a0c23196e1f6",
        "google-gemini-3.5-flash": "9f6cddabc0fb8fd4aeb76e29036c89441e9a56b1c03d539a1cd003006520a6c7",
        "google-gemini-3.5-flash-lite": "e1645f61f762dfaf4cde13d102cd4ab5dc0ecdde8bfe4384c9347078aaa65ec3",
        "google-gemini-3.6-flash": "1977d5a102c298036ab969be96f910962853e35e6a8ec09f7657ec5918f7b094",
    }
    cohere = route_set.route("cohere-command-a-plus-05-2026")
    assert cohere.completion_limit_field == "max_tokens"
    assert cohere.response_format_dialect == "cohere"
    assert route_set.route("google-gemini-3.6-flash").send_temperature is False
    assert route_set.route("google-gemini-3.5-flash-lite").send_temperature is False


def test_qwen_reasoning_route_freezes_json_transport_and_multimodal_capability() -> None:
    route_set = load_route_set(GROQ_REASONING_ROUTE_SET_PATH)
    route = route_set.route("groq-qwen-3.6-27b-json-v2")

    assert route.base_model_id == "Qwen/Qwen3.6-27B"
    assert route.reasoning_effort == "none"
    assert route.reasoning_format == "hidden"
    assert route.response_format == "json_object"
    assert route.strict_schema is False
    assert route.max_tokens == 4096
    assert route.max_rate_limit_retries == 20
    assert route.modalities == ("text", "image")


def test_local_ollama_route_sets_bind_the_17_attested_reference_json_v2_submissions() -> None:
    route_set = load_route_set(LOCAL_OLLAMA_ROUTE_SET_PATH)
    qwen_instruct_route_set = load_route_set(LOCAL_OLLAMA_CANDIDATE_V2_ROUTE_SET_PATH)

    assert route_set.route_set_id == "local-ollama-routes-v1"
    assert len(route_set.routes) == 16
    assert {route.adapter for route in route_set.routes} == {"ollama"}
    assert {route.provider for route in route_set.routes} == {"ollama"}
    assert all(route.base_url == "http://127.0.0.1:11434" for route in route_set.routes)
    assert all(route.response_format == "json_schema" for route in route_set.routes)
    assert all(route.strict_schema is True for route in route_set.routes)
    assert all(str(route.ollama_keep_alive) == "0" for route in route_set.routes)
    assert all(route.ollama_num_ctx == 4096 for route in route_set.routes)
    assert route_set.route("ollama-phi4-mini-3-8b-q4-k-m").model_revision == (
        "78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753"
    )
    assert route_set.route("ollama-qwen2-5vl-7b-q4-k-m").modalities == ("text", "image")
    route_identities = {
        (route.base_model_id, route.model, route.model_revision)
        for route in (*route_set.routes, *qwen_instruct_route_set.routes)
    }
    submission_identities = set()
    for path in (ROOT / "submissions").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        model = payload.get("model", {})
        if model.get("provider") == "ollama" and model.get("harness_revision") == "reference-json-v2":
            submission_identities.add(
                (model["base_model_id"], model["model_name"], model["model_revision"])
            )
    assert route_identities == submission_identities


def test_qwen3_vl_candidate_route_is_isolated_from_the_attested_route_set() -> None:
    route_set = load_route_set(LOCAL_OLLAMA_CANDIDATE_ROUTE_SET_PATH)

    assert route_set.route_set_id == "local-ollama-candidate-routes-v1"
    assert len(route_set.routes) == 1
    candidate = route_set.route("ollama-qwen3-vl-8b")
    assert candidate.base_model_id == "Qwen/Qwen3-VL-8B-Instruct"
    assert candidate.model_revision == (
        "sha256:901cae73216286ea8c5aba8b46d307ff7188f737285ec500c795a12f05225d28"
    )
    assert candidate.modalities == ("text", "image")
    assert str(candidate.ollama_keep_alive) == "0"
    assert candidate.ollama_num_ctx == 4096


def test_qwen3_vl_instruct_candidate_uses_the_non_thinking_artifact() -> None:
    route_set = load_route_set(LOCAL_OLLAMA_CANDIDATE_V2_ROUTE_SET_PATH)

    assert route_set.route_set_id == "local-ollama-candidate-routes-v2"
    assert len(route_set.routes) == 1
    candidate = route_set.route("ollama-qwen3-vl-8b-instruct")
    assert candidate.base_model_id == "Qwen/Qwen3-VL-8B-Instruct"
    assert candidate.model == "qwen3-vl:8b-instruct"
    assert candidate.model_revision == (
        "sha256:0533d74300e4f9bc367d675d4e64ffd073d50ff16a2b4096cc2e8a1cf8c96319"
    )
    assert candidate.modalities == ("text", "image")
    assert str(candidate.ollama_keep_alive) == "0"
    assert candidate.ollama_num_ctx == 4096


def test_self_hosted_planned_model_can_bind_a_reviewed_local_ollama_route(tmp_path: Path) -> None:
    fleet_dir = tmp_path / "fleet"
    fleet_dir.mkdir(parents=True)
    fleet_path = fleet_dir / "public_fleet_v1.yaml"
    fleet_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "medphysbench.model-fleet.v1",
                "fleet_id": "public-fleet-v1",
                "title": "Test fleet",
                "frozen_at": "2026-08-03T12:00:00Z",
                "target_base_model_count": 1,
                "selection_policy_version": "test",
                "models": [
                    {
                        "base_model_id": "microsoft/phi-4",
                        "display_name": "Phi-4",
                        "steward": "Microsoft",
                        "family": "Phi",
                        "openness": "open",
                        "modalities": ["text"],
                        "size_tier": "medium",
                        "planned_routes": ["self_hosted"],
                        "license": "MIT",
                        "source_url": "https://example.invalid/phi-4",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    route_path = fleet_dir / "local_ollama_routes_v1.yaml"
    route_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "medphysbench.model-routes.v1",
                "route_set_id": "local-ollama-routes-v1",
                "fleet_file": "fleet/public_fleet_v1.yaml",
                "fleet_id": "public-fleet-v1",
                "frozen_at": "2026-08-03T12:30:00Z",
                "routes": [
                    {
                        "route_id": "ollama-phi4-14b",
                        "base_model_id": "microsoft/phi-4",
                        "adapter": "ollama",
                        "provider": "ollama",
                        "model": "phi4:14b",
                        "model_revision": "sha256:ac896e5b8b34a1f4efa7b14d7520725140d5512484457fab45d2a4ea14c69dba",
                        "revision_basis": "immutable_digest",
                        "base_url": "http://127.0.0.1:11434",
                        "response_format": "json_schema",
                        "strict_schema": True,
                        "timeout_seconds": 300,
                        "max_tokens": 2048,
                        "access_ttl_seconds": 21600,
                        "modalities": ["text"],
                        "ollama_keep_alive": 0,
                        "ollama_num_ctx": 4096,
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    route_set = load_route_set(route_path, repository_root=tmp_path)
    assert route_set.route("ollama-phi4-14b").base_model_id == "microsoft/phi-4"


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


def test_ollama_receipt_requires_the_reviewed_dependency_set(tmp_path: Path) -> None:
    route_set = load_route_set(LOCAL_OLLAMA_ROUTE_SET_PATH)
    route = route_set.route("ollama-qwen2-5vl-3b")
    path = _write_ollama_receipt(tmp_path, route)
    assert load_access_probe_receipt(path, route_set, repository_root=tmp_path).outcome == "available"

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["probe_dependencies"] = payload["probe_dependencies"][:-1]
    payload = receipt_payload_with_hash({key: value for key, value in payload.items() if key != "content_sha256"})
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RouteQualificationError, match="dependency set mismatch"):
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
    assert first["execution"]["resource_recovery_wait_seconds"] == 0
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
    original_route = {
        **original_routes["routes"][0],
        "send_temperature": False,
        "send_seed": False,
        "completion_limit_field": "max_tokens",
        "response_format_dialect": "cohere",
        "send_reasoning_effort": False,
    }
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
    assert campaign.models[0].send_temperature is False
    assert campaign.models[0].send_seed is False
    assert campaign.models[0].temperature is None
    assert campaign.models[0].seed is None
    assert campaign.models[0].completion_limit_field == "max_tokens"
    assert campaign.models[0].response_format_dialect == "cohere"
    assert campaign.models[0].send_reasoning_effort is False
    assert payload["models"][0]["send_temperature"] is False
    assert payload["models"][0]["send_seed"] is False
    assert payload["models"][0]["temperature"] is None
    assert payload["models"][0]["seed"] is None
    assert payload["models"][0]["completion_limit_field"] == "max_tokens"
    assert payload["models"][0]["response_format_dialect"] == "cohere"
    assert payload["models"][0]["send_reasoning_effort"] is False

    drift_payload = json.loads(json.dumps(payload))
    drift_payload["campaign_id"] = "route-drift-campaign-v2"
    drift_payload["models"][0]["completion_limit_field"] = "max_completion_tokens"
    drift_path = tmp_path / "campaigns" / "route_drift.yaml"
    drift_path.write_text(yaml.safe_dump(drift_payload, sort_keys=False), encoding="utf-8")
    with pytest.raises(CampaignError, match="differs from route"):
        load_campaign(drift_path)

    changed = dict(receipt.payload)
    changed["sanitized_metadata"] = {**changed["sanitized_metadata"], "latency_ms": 43.0}
    changed.pop("content_sha256")
    receipt_path.write_text(json.dumps(receipt_payload_with_hash(changed)), encoding="utf-8")
    with pytest.raises(CampaignError, match="Access receipt hash mismatch"):
        load_campaign(campaign_path)
