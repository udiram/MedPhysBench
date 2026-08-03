from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from medphys_agentbench.adapters.openai_compatible import OpenAICompatibleAdapter
from medphys_agentbench.campaign import (
    CampaignError,
    CampaignExecutionError,
    CampaignSpec,
    ResourceSnapshot,
    _adapter_for_model,
    build_model_command,
    campaign_plan,
    execute_campaign,
    load_campaign,
    resource_limit_failures,
    validate_event_ledger,
    verify_model_completion,
)
from medphys_agentbench.runner import adapter_runtime_settings, create_run_manifest
from medphys_agentbench.scoring import grades_pass, grades_safe, score_attempt, weighted_grade_score

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


def _write_valid_campaign_matrix(campaign: CampaignSpec) -> list[Path]:
    model = campaign.models[0]
    model_dir = campaign.results_dir / campaign.release_id / "llama_3_1_8b_instant"
    paths: list[Path] = []
    for task in campaign.release.load_tasks():
        for attempt_index in range(campaign.attempts):
            attempt_seed = model.seed + attempt_index
            adapter = OpenAICompatibleAdapter(
                model_name=model.model,
                api_key="test-only",
                base_url="https://api.groq.com/openai/v1",
                provider=model.provider,
                temperature=model.temperature,
                seed=attempt_seed,
                max_tokens=model.max_tokens,
                timeout_seconds=model.timeout_seconds,
                response_format=model.response_format,
                strict_schema=model.strict_schema,
                reasoning_effort=model.reasoning_effort,
                artifact_root=ROOT,
                model_revision_override=model.model_revision,
            )
            output: dict[str, object] = {}
            grades = score_attempt(task, output)
            path = model_dir / f"{task.task_id.replace('.', '_').replace('-', '_')}--attempt-{attempt_index + 1}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "attempt_index": attempt_index,
                        "manifest": create_run_manifest(
                            task,
                            adapter,
                            seed=attempt_seed,
                            temperature=model.temperature,
                            max_tokens=model.max_tokens,
                            run_id=f"test-{task.task_id}-{attempt_index}",
                        ).to_dict(),
                        "output": output,
                        "grades": [grade.to_dict() for grade in grades],
                        "passed": grades_pass(grades),
                        "safe": grades_safe(grades),
                        "score": weighted_grade_score(grades),
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            paths.append(path)
    return paths


def test_committed_campaign_binds_five_frozen_models_and_release() -> None:
    campaign = load_campaign(CAMPAIGN_PATH)
    assert campaign.manifest_hash == "6c790df5e849cc9d61b9e5918c5ffddcc2aafc467c1980ea5015bcfc64bb0480"
    assert campaign.release_id == "public-real-workflows-pilot-v0.6"
    assert campaign.fleet_id == "public-fleet-v1"
    assert campaign.attempts == 3
    assert len(campaign.models) == 5
    assert len({model.base_model_id for model in campaign.models}) == 5
    assert campaign.execution.max_parallel_models == 1
    assert campaign.execution.process_isolation is True
    assert campaign.execution.resume is True
    assert campaign.execution.resource_recovery_wait_seconds == 0
    assert campaign.resource_limits.minimum_available_memory_fraction == 0.30


def test_qwen_recovery_campaign_freezes_wait_and_new_result_root() -> None:
    campaign = load_campaign(ROOT / "campaigns" / "qwen3-vl-8b-instruct-openkb-q2-v3.yaml")

    assert campaign.manifest_hash == "9c1212f15ffbe4a25383fcac259c846aba53c007ebbbf53341f79e685ab12c2a"
    assert campaign.execution.resource_recovery_wait_seconds == 30
    assert campaign.results_dir_label == "runs/qwen3-vl-8b-instruct-openkb-q2-v3"
    assert campaign.resource_limits.minimum_available_memory_fraction == 0.35


def test_groq_standard_v2_campaign_binds_two_distinct_frozen_base_models() -> None:
    campaign = load_campaign(ROOT / "campaigns" / "groq-standard-json-v2-q2.yaml")

    assert campaign.manifest_hash == "175af819c9d2e44d27e90fe7e70727c6a7e32cd74280b969b89fe5693169d6ce"
    assert campaign.schema_version == "medeval.campaign.v2"
    assert campaign.release_id == "public-real-workflows-pilot-v0.6"
    assert campaign.attempts == 3
    assert campaign.execution.max_parallel_models == 1
    assert campaign.execution.process_isolation is True
    assert campaign.execution.resume is True
    assert campaign.resource_limits.minimum_available_memory_fraction == 0.35
    assert campaign.resource_limits.minimum_available_memory_gib == 6.0
    assert campaign.resource_limits.minimum_free_disk_gib == 12.0
    assert {model.base_model_id for model in campaign.models} == {
        "meta-llama/Llama-3.3-70B-Instruct",
        "openai/gpt-oss-20b",
    }
    assert {model.route_id for model in campaign.models} == {
        "groq-gpt-oss-20b-json-v2",
        "groq-llama-3.3-70b-json-v2",
    }
    assert {model.max_tokens for model in campaign.models} == {4096}
    assert {model.response_format for model in campaign.models} == {"json_object"}


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
            lambda payload: payload["models"][0].update(
                base_model_id=payload["models"][1]["base_model_id"]
            ),
            "does not match an exact declared route identity",
        ),
        (
            lambda payload: payload["models"][1].update(
                configuration_id="alias-inflation-fixture",
                model="llama-3.1-8b-instant-alias",
                model_revision="llama-3.1-8b-instant-alias@shadow",
                reasoning_effort="high",
                send_reasoning_effort=True,
            ),
            "does not match an exact declared route identity",
        ),
        (
            lambda payload: payload["models"][1].update(configuration_id=payload["models"][0]["configuration_id"]),
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
            lambda payload: payload["models"][0].update(base_url="https://user:password@example.test/v1?token=secret"),
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
    assert command.index("--seed") < command.index("--max-tokens")
    assert command.index("--temperature") < command.index("--max-tokens")
    assert command[command.index("--max-rate-limit-retries") + 1] == "8"
    assert command[command.index("--minimum-available-memory-fraction") + 1] == "0.3"
    assert command[command.index("--minimum-available-memory-gib") + 1] == "4"
    assert command[command.index("--minimum-free-disk-gib") + 1] == "10"
    assert command[command.index("--resource-recovery-wait-seconds") + 1] == "0"
    assert "GROQ_API_KEY" in command
    assert "literal-secret" not in " ".join(command)

    dialect_command = build_model_command(
        campaign,
        replace(
            model,
            seed=None,
            temperature=None,
            send_temperature=False,
            send_seed=False,
            completion_limit_field="max_tokens",
            response_format_dialect="cohere",
            send_reasoning_effort=False,
            reasoning_format="hidden",
        ),
    )
    assert "--omit-temperature" in dialect_command
    assert "--omit-seed" in dialect_command
    assert "--temperature" not in dialect_command
    assert "--seed" not in dialect_command
    assert dialect_command[dialect_command.index("--completion-limit-field") + 1] == "max_tokens"
    assert dialect_command[dialect_command.index("--response-format-dialect") + 1] == "cohere"
    assert "--omit-reasoning-effort" in dialect_command
    assert dialect_command[dialect_command.index("--reasoning-format") + 1] == "hidden"

    plan = campaign_plan(
        campaign,
        environ={"GROQ_API_KEY": "literal-secret"},
        snapshot=_safe_snapshot(),
    )
    assert all(item["credential_present"] is True for item in plan["models"])  # type: ignore[index]
    assert "literal-secret" not in json.dumps(plan)


def test_ollama_completion_verifier_mirrors_child_keep_alive_serialization() -> None:
    campaign = load_campaign(ROOT / "campaigns" / "qwen3-vl-8b-instruct-openkb-q2-v2.yaml")
    model = campaign.models[0]
    command = build_model_command(campaign, model)

    assert command[command.index("--ollama-keep-alive") + 1] == "0"
    assert adapter_runtime_settings(_adapter_for_model(model))["keep_alive"] == "0"


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
            command_runner=lambda _command, _cwd, _environment: 0,
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
            command_runner=lambda command, _cwd, _environment: commands.append(command) or 0,
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

    child_environments: list[dict[str, str]] = []

    def runner(command: list[str], cwd: Path, environment: object) -> int:
        assert cwd == ROOT
        commands.append(command)
        assert isinstance(environment, dict)
        child_environments.append(environment)
        return 0

    report = execute_campaign(
        campaign,
        environ={
            "GROQ_API_KEY": "test-only",
            "UNRELATED_API_KEY": "must-not-reach-child",
            "PATH": "/test/bin",
        },
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
    assert [command[command.index("--model") + 1] for command in commands] == [model.model for model in campaign.models]
    assert all(environment == {"GROQ_API_KEY": "test-only", "PATH": "/test/bin"} for environment in child_environments)

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
            command_runner=lambda command, _cwd, _environment: commands.append(command) or 0,
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
        command_runner=lambda _command, _cwd, _environment: 0,
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
            command_runner=lambda _command, _cwd, _environment: 0,
            completion_verifier=lambda _spec, _model: {"complete": True},
        )


def test_model_failures_are_recorded_without_erasing_later_models(tmp_path: Path) -> None:
    campaign = replace(load_campaign(CAMPAIGN_PATH), results_dir=tmp_path / "runs")
    return_codes = iter([0, 7, 0, 0, 0])
    report = execute_campaign(
        campaign,
        environ={"GROQ_API_KEY": "test-only"},
        snapshot_provider=lambda _path: _safe_snapshot(),
        command_runner=lambda _command, _cwd, _environment: next(return_codes),
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


def test_provider_quota_failure_skips_sibling_routes_without_retries(tmp_path: Path) -> None:
    original = load_campaign(CAMPAIGN_PATH)
    campaign = replace(
        original,
        results_dir=tmp_path / "runs",
        models=original.models[:2],
    )
    commands: list[list[str]] = []

    def runner(command: list[str], _cwd: Path, _environment: object) -> int:
        commands.append(command)
        model_name = command[command.index("--model") + 1]
        model_slug = "".join(character if character.isalnum() else "_" for character in model_name).strip("_").lower()
        error_dir = campaign.results_dir / campaign.release_id / model_slug / "_transport_errors"
        error_dir.mkdir(parents=True, exist_ok=True)
        (error_dir / "quota-error.json").write_text(
            json.dumps(
                {
                    "status": "error",
                    "error_type": "AdapterError",
                    "error": "groq HTTP 429 after bounded retries",
                    "raw_response": {"http_status": 429, "content_redacted": True},
                }
            ),
            encoding="utf-8",
        )
        return 7

    report = execute_campaign(
        campaign,
        environ={"GROQ_API_KEY": "test-only"},
        snapshot_provider=lambda _path: _safe_snapshot(),
        command_runner=runner,
    )

    assert len(commands) == 1
    assert report["status"] == "completed_with_failures"
    assert report["completed_models"] == 0
    assert report["failed_models"] == 2
    assert report["skipped_models"] == 1
    assert report["blocked_providers"] == ["groq"]
    events = validate_event_ledger(
        campaign.results_dir / "_campaigns" / campaign.campaign_id / "events.jsonl",
        expected_campaign_hash=campaign.manifest_hash,
    )
    assert [event["event_type"] for event in events] == [
        "campaign_started",
        "model_started",
        "model_failed",
        "model_skipped_provider_block",
        "campaign_finished",
    ]
    assert events[2]["details"]["failure_kind"] == "provider_quota_blocked"
    assert events[3]["details"]["provider_block"]["reason_code"] == ("provider_quota_or_rate_limit_exhausted")


def test_between_attempt_resource_block_stops_campaign_and_preserves_partial_completion(tmp_path: Path) -> None:
    original = load_campaign(CAMPAIGN_PATH)
    campaign = replace(
        original,
        results_dir=tmp_path / "runs",
        models=(original.models[0],),
        execution=replace(original.execution, continue_on_model_failure=True),
    )
    expected_completion = {
        "complete": False,
        "completed_attempts": 2,
        "missing_attempts": 28,
        "transport_error_count": 0,
    }

    def runner(command: list[str], _cwd: Path, _environment: object) -> int:
        model_name = command[command.index("--model") + 1]
        model_slug = "".join(character if character.isalnum() else "_" for character in model_name).strip("_").lower()
        block_dir = campaign.results_dir / campaign.release_id / model_slug / "_resource_blocks"
        block_dir.mkdir(parents=True, exist_ok=True)
        (block_dir / "memory.json").write_text(
            json.dumps(
                {
                    "schema_version": "medphysbench.resource-block.v1",
                    "task_id": "task-3",
                    "attempt_number": 3,
                    "failures": ["available memory fraction 0.290 is below 0.300"],
                    "resource_snapshot": {"available_memory_fraction": 0.29},
                    "result_committed": False,
                }
            ),
            encoding="utf-8",
        )
        return 1

    with pytest.raises(CampaignExecutionError, match="Per-attempt resource guard stopped"):
        execute_campaign(
            campaign,
            environ={"GROQ_API_KEY": "test-only"},
            snapshot_provider=lambda _path: _safe_snapshot(),
            command_runner=runner,
            completion_verifier=lambda _spec, _model: expected_completion,
        )

    events = validate_event_ledger(
        campaign.results_dir / "_campaigns" / campaign.campaign_id / "events.jsonl",
        expected_campaign_hash=campaign.manifest_hash,
    )
    block = next(event for event in events if event["event_type"] == "resource_blocked")
    assert block["details"]["source"] == "child_attempt_guard"
    assert block["details"]["completion"] == expected_completion
    assert block["details"]["resource_block"]["reason_code"] == "per_attempt_resource_floor_breached"


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
        command_runner=lambda _command, _cwd, _environment: 0,
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


def test_completion_verifier_rejects_contract_grade_and_tree_tampering(tmp_path: Path) -> None:
    original = load_campaign(CAMPAIGN_PATH)
    campaign = replace(
        original,
        results_dir=tmp_path / "runs",
        models=(original.models[0],),
    )
    paths = _write_valid_campaign_matrix(campaign)
    model = campaign.models[0]

    baseline = verify_model_completion(campaign, model)
    assert baseline["complete"] is True
    assert baseline["completed_attempts"] == 30
    assert baseline["invalid_attempt_count"] == 0
    assert baseline["unexpected_attempt_count"] == 0
    assert baseline["artifact_count"] == 30
    assert len(str(baseline["artifact_tree_sha256"])) == 64
    baseline_tree_hash = baseline["artifact_tree_sha256"]

    first_path = paths[0]
    pristine = json.loads(first_path.read_text(encoding="utf-8"))

    wrong_provider = json.loads(json.dumps(pristine))
    wrong_provider["manifest"]["model"]["provider"] = "not-groq"
    first_path.write_text(json.dumps(wrong_provider), encoding="utf-8")
    wrong_provider_completion = verify_model_completion(campaign, model)
    assert wrong_provider_completion["complete"] is False
    assert wrong_provider_completion["artifact_tree_sha256"] != baseline_tree_hash

    wrong_settings = json.loads(json.dumps(pristine))
    wrong_settings["manifest"]["adapter_settings"]["timeout_seconds"] = 1
    first_path.write_text(json.dumps(wrong_settings), encoding="utf-8")
    assert verify_model_completion(campaign, model)["complete"] is False

    wrong_grade = json.loads(json.dumps(pristine))
    wrong_grade["score"] = 1.0
    first_path.write_text(json.dumps(wrong_grade), encoding="utf-8")
    assert verify_model_completion(campaign, model)["complete"] is False

    boolean_score = json.loads(json.dumps(pristine))
    boolean_score["score"] = True
    first_path.write_text(json.dumps(boolean_score), encoding="utf-8")
    assert verify_model_completion(campaign, model)["complete"] is False

    first_path.write_text(json.dumps(pristine), encoding="utf-8")
    extra = first_path.parent / "unexpected-attempt.json"
    extra.write_text("{}", encoding="utf-8")
    completion = verify_model_completion(campaign, model)
    assert completion["complete"] is False
    assert completion["unexpected_attempt_count"] == 1
