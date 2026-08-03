from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from medphys_agentbench.campaign import (
    CampaignError,
    CampaignExecutionError,
    ResourceSnapshot,
    build_model_command,
    campaign_plan,
    execute_campaign,
    load_campaign,
    resource_limit_failures,
    validate_event_ledger,
)

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_PATH = ROOT / "campaigns" / "public_real_workflows_groq_v1.yaml"
GIB = 1024**3


def _safe_snapshot() -> ResourceSnapshot:
    return ResourceSnapshot(
        total_memory_bytes=32 * GIB,
        available_memory_bytes=24 * GIB,
        free_disk_bytes=100 * GIB,
        memory_source="test",
        disk_path="/test",
    )


def _write_variant(tmp_path: Path, mutate: object) -> Path:
    payload = yaml.safe_load(CAMPAIGN_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    mutate(payload)  # type: ignore[operator]
    path = tmp_path / "campaign.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_committed_campaign_binds_five_frozen_models_and_release() -> None:
    campaign = load_campaign(CAMPAIGN_PATH)
    assert campaign.release_id == "public-real-workflows-pilot-v0.6"
    assert campaign.fleet_id == "public-fleet-v1"
    assert campaign.attempts == 3
    assert len(campaign.models) == 5
    assert len({model.base_model_id for model in campaign.models}) == 5
    assert campaign.execution.max_parallel_models == 1
    assert campaign.execution.process_isolation is True
    assert campaign.execution.resume is True
    assert campaign.resource_limits.minimum_available_memory_fraction == 0.30


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda payload: payload.update(release_contract_hash_v2="0" * 64), "release_contract_hash_v2"),
        (lambda payload: payload.update(release_id="wrong-release"), "release_id"),
        (lambda payload: payload.update(attempts=1), "frozen release"),
        (lambda payload: payload.update(results_dir="../outside"), "Invalid campaign manifest"),
        (
            lambda payload: payload["models"][0].update(base_model_id="not/a-frozen-model"),
            "not present",
        ),
        (
            lambda payload: payload["models"][1].update(
                configuration_id=payload["models"][0]["configuration_id"]
            ),
            "configuration_id values must be unique",
        ),
        (
            lambda payload: payload["models"][1].update(model=payload["models"][0]["model"]),
            "unique result directories",
        ),
        (
            lambda payload: payload["models"][0].update(api_key="literal-secret"),
            "secret-like field",
        ),
        (
            lambda payload: payload["models"][0].update(model_revision="gsk" + "_" + "A" * 30),
            "secret-like values",
        ),
        (
            lambda payload: payload["models"][0].update(
                base_url="https://user:password@example.test/v1?token=secret"
            ),
            "must not contain credentials",
        ),
        (
            lambda payload: payload["models"][0].update(adapter="openai-compatible"),
            "must declare base_url",
        ),
    ],
)
def test_campaign_rejects_contract_drift_and_secret_surfaces(
    tmp_path: Path,
    mutate: object,
    message: str,
) -> None:
    path = _write_variant(tmp_path, mutate)
    with pytest.raises(CampaignError, match=message):
        load_campaign(path)


def test_command_is_shell_free_resumable_and_never_contains_secret_value() -> None:
    campaign = load_campaign(CAMPAIGN_PATH)
    model = campaign.models[0]
    command = build_model_command(campaign, model)
    assert isinstance(command, list)
    assert command[:3] == [command[0], "-m", "medphys_agentbench.cli"]
    assert "--resume" in command
    assert "--fail-fast" in command
    assert "--best-effort-schema" in command
    assert "GROQ_API_KEY" in command
    assert "literal-secret" not in " ".join(command)

    plan = campaign_plan(
        campaign,
        environ={"GROQ_API_KEY": "literal-secret"},
        snapshot=_safe_snapshot(),
    )
    assert all(item["credential_present"] is True for item in plan["models"])  # type: ignore[index]
    assert "literal-secret" not in json.dumps(plan)


def test_resource_guard_fails_closed_for_unknown_low_memory_and_disk() -> None:
    campaign = load_campaign(CAMPAIGN_PATH)
    unknown = ResourceSnapshot(None, None, 100 * GIB, "unavailable", "/test")
    assert resource_limit_failures(unknown, campaign.resource_limits) == [
        "available system memory could not be measured"
    ]

    pressured = ResourceSnapshot(32 * GIB, 3 * GIB, 2 * GIB, "test", "/test")
    failures = resource_limit_failures(pressured, campaign.resource_limits)
    assert any("memory fraction" in failure for failure in failures)
    assert any("available memory" in failure for failure in failures)
    assert any("free disk" in failure for failure in failures)


def test_dry_run_writes_no_state_and_requires_no_credential(tmp_path: Path) -> None:
    campaign = replace(load_campaign(CAMPAIGN_PATH), results_dir=tmp_path / "runs")
    report = execute_campaign(
        campaign,
        dry_run=True,
        environ={},
        snapshot_provider=lambda _path: _safe_snapshot(),
    )
    assert report["dry_run"] is True
    assert len(report["commands"]) == 5  # type: ignore[arg-type]
    assert not campaign.results_dir.exists()


def test_execution_requires_credentials_before_writing_state(tmp_path: Path) -> None:
    campaign = replace(load_campaign(CAMPAIGN_PATH), results_dir=tmp_path / "runs")
    with pytest.raises(CampaignExecutionError, match="GROQ_API_KEY"):
        execute_campaign(
            campaign,
            environ={},
            snapshot_provider=lambda _path: _safe_snapshot(),
            command_runner=lambda _command, _cwd: 0,
        )
    assert not campaign.results_dir.exists()


def test_initial_resource_failure_writes_only_a_hash_chained_preflight_receipt(tmp_path: Path) -> None:
    campaign = replace(load_campaign(CAMPAIGN_PATH), results_dir=tmp_path / "runs")
    low = ResourceSnapshot(32 * GIB, 2 * GIB, 100 * GIB, "test", "/test")
    commands: list[list[str]] = []
    with pytest.raises(CampaignExecutionError, match="resource preflight failed"):
        execute_campaign(
            campaign,
            environ={"GROQ_API_KEY": "test-only"},
            snapshot_provider=lambda _path: low,
            command_runner=lambda command, _cwd: commands.append(command) or 0,
        )
    assert commands == []
    state_dir = campaign.results_dir / "_campaigns" / campaign.campaign_id
    assert (state_dir / "campaign.json").is_file()
    events = validate_event_ledger(
        state_dir / "events.jsonl",
        expected_campaign_hash=campaign.manifest_hash,
    )
    assert [event["event_type"] for event in events] == ["campaign_preflight_failed"]


def test_campaign_executes_serially_and_writes_hash_chained_resume_state(tmp_path: Path) -> None:
    campaign = replace(load_campaign(CAMPAIGN_PATH), results_dir=tmp_path / "runs")
    commands: list[list[str]] = []

    def runner(command: list[str], cwd: Path) -> int:
        assert cwd == ROOT
        commands.append(command)
        return 0

    report = execute_campaign(
        campaign,
        environ={"GROQ_API_KEY": "test-only"},
        snapshot_provider=lambda _path: _safe_snapshot(),
        command_runner=runner,
        completion_verifier=lambda _spec, _model: {
            "complete": True,
            "expected_attempts": 30,
            "completed_attempts": 30,
            "missing_attempts": 0,
            "invalid_attempt_count": 0,
            "transport_error_count": 0,
        },
    )
    assert report["status"] == "completed"
    assert report["completed_models"] == 5
    assert len(commands) == 5
    assert [command[command.index("--model") + 1] for command in commands] == [
        model.model for model in campaign.models
    ]

    state_dir = campaign.results_dir / "_campaigns" / campaign.campaign_id
    state = json.loads((state_dir / "campaign.json").read_text(encoding="utf-8"))
    assert state["campaign_manifest_sha256"] == campaign.manifest_hash
    events = validate_event_ledger(
        state_dir / "events.jsonl",
        expected_campaign_hash=campaign.manifest_hash,
    )
    assert len(events) == 12
    assert [event["event_type"] for event in events].count("model_started") == 5
    assert [event["event_type"] for event in events].count("model_completed") == 5


def test_resource_pressure_stops_before_next_model_and_is_recorded(tmp_path: Path) -> None:
    campaign = replace(load_campaign(CAMPAIGN_PATH), results_dir=tmp_path / "runs")
    snapshots = iter(
        [
            _safe_snapshot(),
            _safe_snapshot(),
            ResourceSnapshot(32 * GIB, 2 * GIB, 100 * GIB, "test", "/test"),
        ]
    )
    commands: list[list[str]] = []
    with pytest.raises(CampaignExecutionError, match="Resource guard stopped"):
        execute_campaign(
            campaign,
            environ={"GROQ_API_KEY": "test-only"},
            snapshot_provider=lambda _path: next(snapshots),
            command_runner=lambda command, _cwd: commands.append(command) or 0,
            completion_verifier=lambda _spec, _model: {"complete": True},
        )
    assert len(commands) == 1
    events = validate_event_ledger(
        campaign.results_dir / "_campaigns" / campaign.campaign_id / "events.jsonl",
        expected_campaign_hash=campaign.manifest_hash,
    )
    assert events[-1]["event_type"] == "resource_blocked"


def test_event_tampering_and_manifest_mutation_block_resume(tmp_path: Path) -> None:
    campaign = replace(
        load_campaign(CAMPAIGN_PATH),
        results_dir=tmp_path / "runs",
        models=(load_campaign(CAMPAIGN_PATH).models[0],),
    )
    execute_campaign(
        campaign,
        environ={"GROQ_API_KEY": "test-only"},
        snapshot_provider=lambda _path: _safe_snapshot(),
        command_runner=lambda _command, _cwd: 0,
        completion_verifier=lambda _spec, _model: {"complete": True},
    )
    state_dir = campaign.results_dir / "_campaigns" / campaign.campaign_id
    ledger = state_dir / "events.jsonl"
    original = ledger.read_text(encoding="utf-8")
    ledger.write_text(original.replace("campaign_started", "campaign_tampered", 1), encoding="utf-8")
    with pytest.raises(CampaignError, match="content hash mismatch"):
        validate_event_ledger(ledger, expected_campaign_hash=campaign.manifest_hash)

    ledger.write_text(original, encoding="utf-8")
    changed = replace(campaign, manifest_hash="0" * 64)
    with pytest.raises(CampaignError, match="immutable campaign state differs"):
        execute_campaign(
            changed,
            environ={"GROQ_API_KEY": "test-only"},
            snapshot_provider=lambda _path: _safe_snapshot(),
            command_runner=lambda _command, _cwd: 0,
            completion_verifier=lambda _spec, _model: {"complete": True},
        )


def test_model_failures_are_recorded_without_erasing_later_models(tmp_path: Path) -> None:
    campaign = replace(load_campaign(CAMPAIGN_PATH), results_dir=tmp_path / "runs")
    return_codes = iter([0, 7, 0, 0, 0])
    report = execute_campaign(
        campaign,
        environ={"GROQ_API_KEY": "test-only"},
        snapshot_provider=lambda _path: _safe_snapshot(),
        command_runner=lambda _command, _cwd: next(return_codes),
        completion_verifier=lambda _spec, _model: {"complete": True},
    )
    assert report["status"] == "completed_with_failures"
    assert report["completed_models"] == 4
    assert report["failed_models"] == 1
    events = validate_event_ledger(
        campaign.results_dir / "_campaigns" / campaign.campaign_id / "events.jsonl",
        expected_campaign_hash=campaign.manifest_hash,
    )
    assert [event["event_type"] for event in events].count("model_failed") == 1


def test_zero_exit_without_canonical_matrix_is_not_marked_complete(tmp_path: Path) -> None:
    campaign = replace(
        load_campaign(CAMPAIGN_PATH),
        results_dir=tmp_path / "runs",
        models=(load_campaign(CAMPAIGN_PATH).models[0],),
    )
    report = execute_campaign(
        campaign,
        environ={"GROQ_API_KEY": "test-only"},
        snapshot_provider=lambda _path: _safe_snapshot(),
        command_runner=lambda _command, _cwd: 0,
    )
    assert report["status"] == "completed_with_failures"
    assert report["completed_models"] == 0
    assert report["failed_models"] == 1
    events = validate_event_ledger(
        campaign.results_dir / "_campaigns" / campaign.campaign_id / "events.jsonl",
        expected_campaign_hash=campaign.manifest_hash,
    )
    assert events[-2]["event_type"] == "model_failed"
    assert events[-2]["details"]["failure_kind"] == "canonical_matrix_incomplete"
