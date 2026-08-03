"""CLI for validating tasks, running single trials, and producing leaderboard summaries."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .adapters.base import AgentAdapter
from .adapters.ollama import AdapterError, OllamaAdapter, resolve_ollama_model_revision
from .adapters.openai_compatible import (
    OpenAICompatibleAdapter,
    ProviderOutputContractError,
    UnsupportedCapabilityError,
)
from .adapters.recorded import RecordedOutputAdapter
from .adapters.reference import DevelopmentReferenceAgent
from .campaign import CampaignError, CampaignExecutionError, campaign_plan, execute_campaign, load_campaign
from .campaign_generation import generate_campaign_payload, write_campaign_manifest
from .contracts import ModelDescriptor, TaskSpec
from .json_utils import stable_hash
from .recorded_capture import sealed_batch_payload, validate_recorded_batch
from .release_loader import load_release
from .reporting import summarize_release, write_summary
from .route_qualification import RouteQualificationError, load_access_probe_receipt, load_route_set
from .runner import (
    SCORING_REVISION,
    adapter_runtime_settings,
    create_run_manifest,
    grader_hash_for_task,
    prompt_hash_for_task,
    run_trial,
    runtime_task_hash_for_task,
    system_prompt_hash,
    tool_schema_hash_for_task,
)
from .scoring import grades_pass, grades_safe, score_attempt, weighted_grade_score
from .task_loader import load_task


def main() -> None:
    parser = argparse.ArgumentParser(prog="medphys-bench")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="Validate a task pack against the v1 contract.")
    validate.add_argument("task_file", type=Path)

    demo = subparsers.add_parser("demo", help="Run the development-only reference agent against a dev task pack.")
    demo.add_argument("task_file", type=Path)

    validate_release = subparsers.add_parser("validate-release", help="Validate a benchmark release manifest.")
    validate_release.add_argument("release_file", type=Path)

    validate_campaign = subparsers.add_parser(
        "validate-campaign",
        help="Validate a serial campaign manifest and print its resource/credential plan.",
    )
    validate_campaign.add_argument("campaign_file", type=Path)

    run_campaign = subparsers.add_parser(
        "run-campaign",
        help="Run a frozen multi-model campaign serially with process isolation and immutable resume state.",
    )
    run_campaign.add_argument("campaign_file", type=Path)
    run_campaign.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the exact redacted execution plan without writing state or contacting providers.",
    )

    generate_campaign = subparsers.add_parser(
        "generate-campaign",
        help="Generate an immutable v2 campaign from exact routes and unexpired access receipts.",
    )
    generate_campaign.add_argument("route_set_file", type=Path)
    generate_campaign.add_argument("release_file")
    generate_campaign.add_argument("--route-id", action="append", required=True)
    generate_campaign.add_argument(
        "--receipt",
        action="append",
        required=True,
        metavar="ROUTE_ID=PATH",
        help="Bind one selected route to one immutable access-probe receipt.",
    )
    generate_campaign.add_argument("--campaign-id", required=True)
    generate_campaign.add_argument("--results-dir", required=True)
    generate_campaign.add_argument("--output", type=Path, required=True)
    generate_campaign.add_argument(
        "--as-of",
        required=True,
        help="Explicit RFC 3339 generation instant used for deterministic receipt expiry checks.",
    )
    generate_campaign.add_argument("--seed", type=int, default=20260731)
    generate_campaign.add_argument("--temperature", type=float, default=0.0)
    generate_campaign.add_argument(
        "--minimum-available-memory-fraction",
        type=float,
        default=0.30,
        help="Stop before a model call when available memory falls below this fraction (default: 0.30).",
    )
    generate_campaign.add_argument(
        "--minimum-available-memory-gib",
        type=float,
        default=4,
        help="Stop before a model call when available memory falls below this GiB floor (default: 4).",
    )
    generate_campaign.add_argument(
        "--minimum-free-disk-gib",
        type=float,
        default=10,
        help="Stop before a model call when free disk falls below this GiB floor (default: 10).",
    )
    generate_campaign.add_argument(
        "--allow-unknown-quota",
        action="store_true",
        help="Record an explicit override when the provider does not expose quota state.",
    )

    run = subparsers.add_parser("run", help="Run a single task against an adapter/model pair.")
    run.add_argument("task_file", type=Path)
    run.add_argument(
        "--adapter",
        choices=["ollama", "groq", "openai", "openai-compatible"],
        required=True,
    )
    run.add_argument("--model", required=True)
    run.add_argument(
        "--model-revision",
        help="Exact provider revision or local artifact digest; Ollama resolves /api/tags when omitted.",
    )
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--base-url")
    run.add_argument("--api-key-env")
    run.add_argument("--provider")
    run.add_argument("--response-format", choices=["json_schema", "json_object"], default="json_schema")
    run.add_argument("--best-effort-schema", action="store_true")
    run.add_argument("--reasoning-effort", choices=["none", "minimal", "low", "medium", "high"])
    run.add_argument("--reasoning-format", choices=["hidden", "parsed", "raw"])
    run.add_argument("--timeout", type=int, default=300)
    run.add_argument("--seed", type=int, default=20260731)
    run.add_argument("--temperature", type=float, default=0.0)
    run.add_argument("--max-tokens", type=int, default=1024)
    run.add_argument("--max-rate-limit-retries", type=int, default=8)
    run.add_argument("--omit-temperature", action="store_true")
    run.add_argument("--omit-seed", action="store_true")
    run.add_argument(
        "--completion-limit-field",
        choices=["max_completion_tokens", "max_tokens"],
        default="max_completion_tokens",
    )
    run.add_argument(
        "--response-format-dialect",
        choices=["openai", "cohere", "omit"],
        default="openai",
    )
    run.add_argument("--omit-reasoning-effort", action="store_true")
    run.add_argument(
        "--ollama-keep-alive",
        default="0",
        help="Ollama model residency after a request; 0 unloads immediately (default: 0).",
    )
    run.add_argument("--ollama-num-ctx", type=int, default=4096)

    run_release = subparsers.add_parser("run-release", help="Run every task in a release for one or more models.")
    run_release.add_argument("release_file", type=Path)
    run_release.add_argument(
        "--adapter",
        choices=["ollama", "groq", "openai", "openai-compatible"],
        required=True,
    )
    run_release.add_argument("--model", action="append", required=True)
    run_release.add_argument(
        "--model-revision",
        help=("Exact revision for a single --model; Ollama resolves each /api/tags digest when omitted."),
    )
    run_release.add_argument("--results-dir", type=Path, default=Path("runs"))
    run_release.add_argument(
        "--attempts",
        type=int,
        help="Attempts per task; defaults to the frozen release contract.",
    )
    run_release.add_argument("--base-url")
    run_release.add_argument("--api-key-env")
    run_release.add_argument("--provider")
    run_release.add_argument("--response-format", choices=["json_schema", "json_object"], default="json_schema")
    run_release.add_argument("--best-effort-schema", action="store_true")
    run_release.add_argument("--reasoning-effort", choices=["none", "minimal", "low", "medium", "high"])
    run_release.add_argument("--reasoning-format", choices=["hidden", "parsed", "raw"])
    run_release.add_argument("--timeout", type=int, default=300)
    run_release.add_argument("--seed", type=int, default=20260731)
    run_release.add_argument("--temperature", type=float, default=0.0)
    run_release.add_argument("--max-tokens", type=int, default=1024)
    run_release.add_argument("--max-rate-limit-retries", type=int, default=8)
    run_release.add_argument("--omit-temperature", action="store_true")
    run_release.add_argument("--omit-seed", action="store_true")
    run_release.add_argument(
        "--completion-limit-field",
        choices=["max_completion_tokens", "max_tokens"],
        default="max_completion_tokens",
    )
    run_release.add_argument(
        "--response-format-dialect",
        choices=["openai", "cohere", "omit"],
        default="openai",
    )
    run_release.add_argument("--omit-reasoning-effort", action="store_true")
    run_release.add_argument(
        "--ollama-keep-alive",
        default="0",
        help="Ollama model residency after a request; 0 unloads immediately (default: 0).",
    )
    run_release.add_argument("--ollama-num-ctx", type=int, default=4096)
    run_release.add_argument("--fail-fast", action="store_true")
    run_release.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Continue only missing immutable attempt keys. Existing artifacts are validated "
            "against the exact task, model, settings, and scoring contract before any new request."
        ),
    )

    summarize = subparsers.add_parser("summarize", help="Build leaderboard JSON from a completed release run.")
    summarize.add_argument("release_file", type=Path)
    summarize.add_argument("--results-dir", type=Path, default=Path("runs"))
    summarize.add_argument("--output", type=Path, required=True)
    summarize.add_argument("--expected-attempts", type=int)

    export_runtime = subparsers.add_parser(
        "export-runtime", help="Export sealed model-visible tasks for an external evaluation surface."
    )
    export_runtime.add_argument("release_file", type=Path)
    export_runtime.add_argument("--output", type=Path, required=True)

    score_recorded = subparsers.add_parser(
        "score-recorded-batch", help="Score a task-id to JSON-output mapping from a declared pilot surface."
    )
    score_recorded.add_argument("release_file", type=Path)
    score_recorded.add_argument("batch_file", type=Path)
    score_recorded.add_argument("--model", required=True)
    score_recorded.add_argument("--model-revision", required=True)
    score_recorded.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high", "xhigh", "max", "ultra"],
        required=True,
    )
    score_recorded.add_argument(
        "--attempt-index",
        type=int,
        default=1,
        help="One-based immutable attempt number to write (default: 1).",
    )
    score_recorded.add_argument("--results-dir", type=Path, default=Path("runs"))

    args = parser.parse_args()
    if args.command == "validate":
        task = load_task(args.task_file)
        # Validation output is deliberately safe to print in CI logs. The full
        # authoring manifest may contain grader configuration or development gold.
        print(
            json.dumps(
                {
                    "valid": True,
                    "task_id": task.task_id,
                    "version": task.version,
                    "access_class": task.access_class.value,
                    "runtime_task": task.runtime_task().to_dict(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    if args.command == "demo":
        task = load_task(args.task_file)
        output = task.grading.get("development_reference_output")
        if not isinstance(output, dict):
            raise SystemExit("The demo command requires grading.development_reference_output in a dev task.")
        result = run_trial(task, DevelopmentReferenceAgent(output=output))
        payload = {**result.to_dict(), "status": "completed", "attempt_index": 0}
        print(json.dumps(payload, indent=2, sort_keys=True))
        if not result.passed:
            raise SystemExit(1)
        return

    if args.command == "validate-release":
        release = load_release(args.release_file)
        tasks = release.load_tasks()
        print(
            json.dumps(
                {
                    "valid": True,
                    "release_id": release.release_id,
                    "expected_attempts_per_task": release.expected_attempts_per_task,
                    "task_count": len(tasks),
                    "task_ids": [task.task_id for task in tasks],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    if args.command == "validate-campaign":
        try:
            campaign = load_campaign(args.campaign_file)
            print(json.dumps(campaign_plan(campaign), indent=2, sort_keys=True))
        except CampaignError as error:
            raise SystemExit(str(error)) from error
        return

    if args.command == "run-campaign":
        try:
            campaign = load_campaign(args.campaign_file)
            report = execute_campaign(campaign, dry_run=args.dry_run)
            print(json.dumps(report, indent=2, sort_keys=True))
        except (CampaignError, CampaignExecutionError) as error:
            raise SystemExit(str(error)) from error
        return

    if args.command == "generate-campaign":
        try:
            route_set = load_route_set(args.route_set_file)
            receipt_paths = _parse_route_receipt_bindings(args.receipt)
            if set(receipt_paths) != set(args.route_id):
                raise RouteQualificationError("Every selected route must have exactly one --receipt binding.")
            receipts = {
                route_id: load_access_probe_receipt(path, route_set)
                for route_id, path in receipt_paths.items()
            }
            as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
            payload = generate_campaign_payload(
                route_set,
                receipts,
                route_ids=args.route_id,
                release_file=args.release_file,
                campaign_id=args.campaign_id,
                results_dir=args.results_dir,
                as_of=as_of,
                seed=args.seed,
                temperature=args.temperature,
                allow_unknown_quota=args.allow_unknown_quota,
                minimum_available_memory_fraction=args.minimum_available_memory_fraction,
                minimum_available_memory_gib=args.minimum_available_memory_gib,
                minimum_free_disk_gib=args.minimum_free_disk_gib,
            )
            created = write_campaign_manifest(args.output, payload)
        except (RouteQualificationError, ValueError) as error:
            raise SystemExit(str(error)) from error
        print(
            json.dumps(
                {
                    "valid": True,
                    "created": created,
                    "campaign_id": payload["campaign_id"],
                    "route_count": len(payload["models"]),
                    "output": str(args.output),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    if args.command == "run":
        task = load_task(args.task_file)
        model_revision = _resolve_model_revision(
            args.adapter,
            args.model,
            args.model_revision,
            args.base_url,
            args.timeout,
        )
        adapter = _build_adapter(
            args.adapter,
            args.model,
            args.base_url,
            args.timeout,
            seed=args.seed,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            max_rate_limit_retries=args.max_rate_limit_retries,
            send_temperature=not args.omit_temperature,
            send_seed=not args.omit_seed,
            completion_limit_field=args.completion_limit_field,
            response_format_dialect=args.response_format_dialect,
            send_reasoning_effort=not args.omit_reasoning_effort,
            api_key_env=args.api_key_env,
            provider=args.provider,
            response_format=args.response_format,
            strict_schema=not args.best_effort_schema,
            reasoning_effort=args.reasoning_effort,
            reasoning_format=args.reasoning_format,
            ollama_keep_alive=args.ollama_keep_alive,
            ollama_num_ctx=args.ollama_num_ctx,
            model_revision_override=model_revision,
        )
        result = run_trial(
            task,
            adapter,
            seed=None if args.omit_seed else args.seed,
            temperature=None if args.omit_temperature else args.temperature,
            max_tokens=args.max_tokens,
        )
        payload = {**result.to_dict(), "status": "completed", "attempt_index": 0}
        _write_json(args.output, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        if not result.safe:
            raise SystemExit(1)
        return

    if args.command == "run-release":
        release = load_release(args.release_file)
        tasks = release.load_tasks()
        attempts = args.attempts if args.attempts is not None else release.expected_attempts_per_task
        if attempts < 1:
            raise SystemExit("--attempts must be at least 1.")
        if args.model_revision and len(args.model) != 1:
            raise SystemExit("--model-revision can only be used with exactly one --model.")
        model_revisions = {
            model_name: _resolve_model_revision(
                args.adapter,
                model_name,
                args.model_revision,
                args.base_url,
                args.timeout,
            )
            for model_name in args.model
        }

        output_catalog: dict[str, list[Path]] = {}
        for model_name in args.model:
            model_dir = args.results_dir / release.release_id / _slugify(model_name)
            output_catalog[model_name] = [
                model_dir / f"{_slugify(task.task_id)}--attempt-{attempt_index + 1}.json"
                for task in tasks
                for attempt_index in range(attempts)
            ]
        existing_paths = [path for paths in output_catalog.values() for path in paths if path.exists()]
        if existing_paths and not args.resume:
            raise SystemExit(
                "Release result artifacts are immutable; refusing to overwrite "
                f"{len(existing_paths)} existing file(s), beginning with {existing_paths[0]}. "
                "Use --resume to validate and skip exact existing attempts, or use a new "
                "results directory/model revision label."
            )

        if existing_paths:
            for model_name in args.model:
                resume_adapter = _build_adapter(
                    args.adapter,
                    model_name,
                    args.base_url,
                    args.timeout,
                    seed=args.seed,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    max_rate_limit_retries=args.max_rate_limit_retries,
                    send_temperature=not args.omit_temperature,
                    send_seed=not args.omit_seed,
                    completion_limit_field=args.completion_limit_field,
                    response_format_dialect=args.response_format_dialect,
                    send_reasoning_effort=not args.omit_reasoning_effort,
                    api_key_env=args.api_key_env,
                    provider=args.provider,
                    response_format=args.response_format,
                    strict_schema=not args.best_effort_schema,
                    reasoning_effort=args.reasoning_effort,
                    reasoning_format=args.reasoning_format,
                    ollama_keep_alive=args.ollama_keep_alive,
                    ollama_num_ctx=args.ollama_num_ctx,
                    model_revision_override=model_revisions[model_name],
                )
                descriptor = resume_adapter.model_descriptor()
                settings = adapter_runtime_settings(resume_adapter)
                model_dir = args.results_dir / release.release_id / _slugify(model_name)
                for task in tasks:
                    for attempt_index in range(attempts):
                        output_path = model_dir / (f"{_slugify(task.task_id)}--attempt-{attempt_index + 1}.json")
                        if output_path.exists():
                            _validate_resumable_attempt(
                                output_path,
                                task=task,
                                model_descriptor=descriptor,
                                adapter_settings=settings,
                                attempt_index=attempt_index,
                                seed=None if args.omit_seed else args.seed + attempt_index,
                                temperature=None if args.omit_temperature else args.temperature,
                                max_tokens=args.max_tokens,
                            )

        for model_name in args.model:
            model_slug = _slugify(model_name)
            model_dir = args.results_dir / release.release_id / model_slug
            model_dir.mkdir(parents=True, exist_ok=True)
            for task in tasks:
                for attempt_index in range(attempts):
                    attempt_seed = args.seed if args.omit_seed else args.seed + attempt_index
                    output_path = model_dir / (f"{_slugify(task.task_id)}--attempt-{attempt_index + 1}.json")
                    if output_path.exists():
                        print(
                            json.dumps(
                                {
                                    "model": model_name,
                                    "task_id": task.task_id,
                                    "attempt": attempt_index + 1,
                                    "status": "skipped_existing",
                                    "output_file": str(output_path),
                                },
                                sort_keys=True,
                            )
                        )
                        continue
                    adapter = _build_adapter(
                        args.adapter,
                        model_name,
                        args.base_url,
                        args.timeout,
                        seed=attempt_seed,
                        temperature=args.temperature,
                        max_tokens=args.max_tokens,
                        max_rate_limit_retries=args.max_rate_limit_retries,
                        send_temperature=not args.omit_temperature,
                        send_seed=not args.omit_seed,
                        completion_limit_field=args.completion_limit_field,
                        response_format_dialect=args.response_format_dialect,
                        send_reasoning_effort=not args.omit_reasoning_effort,
                        api_key_env=args.api_key_env,
                        provider=args.provider,
                        response_format=args.response_format,
                        strict_schema=not args.best_effort_schema,
                        reasoning_effort=args.reasoning_effort,
                        reasoning_format=args.reasoning_format,
                        ollama_keep_alive=args.ollama_keep_alive,
                        ollama_num_ctx=args.ollama_num_ctx,
                        model_revision_override=model_revisions[model_name],
                    )
                    run_id = str(uuid4())
                    try:
                        result = run_trial(
                            task,
                            adapter,
                            seed=None if args.omit_seed else attempt_seed,
                            temperature=None if args.omit_temperature else args.temperature,
                            max_tokens=args.max_tokens,
                            run_id=run_id,
                        )
                        payload = {
                            **result.to_dict(),
                            "status": "completed",
                            "attempt_index": attempt_index,
                        }
                    except (UnsupportedCapabilityError, ProviderOutputContractError) as error:
                        grades = score_attempt(task, {})
                        contract_trace = list(error.trace) if isinstance(error, ProviderOutputContractError) else []
                        contract_receipt = (
                            dict(error.raw_response) if isinstance(error, ProviderOutputContractError) else {}
                        )
                        contract_duration = (
                            error.duration_seconds if isinstance(error, ProviderOutputContractError) else None
                        )
                        failure_kind = (
                            "unsupported_required_modality"
                            if isinstance(error, UnsupportedCapabilityError)
                            else "provider_output_contract_failure"
                        )
                        payload = {
                            "status": "completed",
                            "attempt_index": attempt_index,
                            "capability_failure": isinstance(error, UnsupportedCapabilityError),
                            "model_failure_kind": failure_kind,
                            "error_type": type(error).__name__,
                            "error": str(error),
                            "passed": grades_pass(grades),
                            "safe": grades_safe(grades),
                            "score": weighted_grade_score(grades),
                            "manifest": create_run_manifest(
                                task,
                                adapter,
                                seed=None if args.omit_seed else attempt_seed,
                                temperature=None if args.omit_temperature else args.temperature,
                                max_tokens=args.max_tokens,
                                run_id=run_id,
                            ).to_dict(),
                            "output": {},
                            "grades": [grade.to_dict() for grade in grades],
                            "trace": [
                                *contract_trace,
                                {
                                    "event": failure_kind,
                                    "provider": adapter.model_descriptor().provider,
                                    "model": adapter.model_descriptor().model_name,
                                },
                            ],
                            "raw_response": contract_receipt,
                            "duration_seconds": contract_duration or 0.0,
                        }
                    except AdapterError as error:
                        payload = {
                            "status": "error",
                            "attempt_index": attempt_index,
                            "error_type": type(error).__name__,
                            "error": str(error),
                            "passed": False,
                            "safe": False,
                            "score": 0.0,
                            "manifest": create_run_manifest(
                                task,
                                adapter,
                                seed=None if args.omit_seed else attempt_seed,
                                temperature=None if args.omit_temperature else args.temperature,
                                max_tokens=args.max_tokens,
                                run_id=run_id,
                            ).to_dict(),
                            "output": {},
                            "grades": [],
                            "trace": [],
                            "raw_response": {},
                            "duration_seconds": 0.0,
                        }
                        error_path = (
                            model_dir
                            / "_transport_errors"
                            / (f"{_slugify(task.task_id)}--attempt-{attempt_index + 1}--{run_id}.json")
                        )
                        _write_json_exclusive(error_path, payload)
                        print(
                            json.dumps(
                                {
                                    "model": model_name,
                                    "task_id": task.task_id,
                                    "attempt": attempt_index + 1,
                                    "status": "transport_error_uncommitted",
                                    "error_file": str(error_path),
                                },
                                sort_keys=True,
                            )
                        )
                        if args.fail_fast:
                            raise
                        continue
                    except Exception as error:
                        error_path = (
                            model_dir
                            / "_internal_errors"
                            / (f"{_slugify(task.task_id)}--attempt-{attempt_index + 1}--{run_id}.json")
                        )
                        _write_json_exclusive(
                            error_path,
                            {
                                "schema_version": "medphysbench.internal-error.v1",
                                "run_id": run_id,
                                "task_id": task.task_id,
                                "attempt_index": attempt_index,
                                "model": asdict(adapter.model_descriptor()),
                                "error_type": type(error).__name__,
                                "error": str(error),
                            },
                        )
                        raise RuntimeError(
                            f"Internal campaign error for {model_name} on {task.task_id}; recorded at {error_path}."
                        ) from error
                    try:
                        _write_json_exclusive(output_path, payload)
                        print(
                            json.dumps(
                                {
                                    "model": model_name,
                                    "task_id": task.task_id,
                                    "attempt": attempt_index + 1,
                                    "status": payload["status"],
                                    "passed": payload["passed"],
                                    "safe": payload["safe"],
                                    "output_file": str(output_path),
                                },
                                sort_keys=True,
                            )
                        )
                    except FileExistsError:
                        _validate_resumable_attempt(
                            output_path,
                            task=task,
                            model_descriptor=adapter.model_descriptor(),
                            adapter_settings=adapter_runtime_settings(adapter),
                            attempt_index=attempt_index,
                            seed=None if args.omit_seed else attempt_seed,
                            temperature=None if args.omit_temperature else args.temperature,
                            max_tokens=args.max_tokens,
                        )
                        print(
                            json.dumps(
                                {
                                    "model": model_name,
                                    "task_id": task.task_id,
                                    "attempt": attempt_index + 1,
                                    "status": "skipped_existing_race_validated",
                                    "output_file": str(output_path),
                                },
                                sort_keys=True,
                            )
                        )
        return

    if args.command == "summarize":
        release = load_release(args.release_file)
        summary = summarize_release(
            release,
            args.results_dir,
            expected_attempts_per_task=args.expected_attempts,
        )
        write_summary(summary, args.output)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return

    if args.command == "export-runtime":
        release = load_release(args.release_file)
        tasks = release.load_tasks()
        payload = sealed_batch_payload(release.release_id, tasks)
        _write_json(args.output, payload)
        print(json.dumps({"output": str(args.output), "task_count": len(tasks)}, sort_keys=True))
        return

    if args.command == "score-recorded-batch":
        if args.attempt_index < 1:
            raise SystemExit("--attempt-index must be at least 1.")
        release = load_release(args.release_file)
        batch = json.loads(args.batch_file.read_text(encoding="utf-8"))
        outputs = batch.get("outputs") if isinstance(batch, dict) else None
        if not isinstance(outputs, dict):
            raise SystemExit("Recorded batch must contain an object named 'outputs'.")
        tasks = release.load_tasks()
        try:
            capture_metadata = validate_recorded_batch(
                batch,
                release_id=release.release_id,
                tasks=tasks,
                model=args.model,
                model_revision=args.model_revision,
                reasoning_effort=args.reasoning_effort,
                attempt_index=args.attempt_index,
            )
        except ValueError as error:
            raise SystemExit(str(error)) from error
        adapter = RecordedOutputAdapter(
            outputs=outputs,
            model_name=args.model,
            model_revision=args.model_revision,
            reasoning_effort=args.reasoning_effort,
            capture_metadata=capture_metadata,
            capture_schema_version=str(batch.get("schema_version")),
        )
        model_slug = _slugify(f"{args.model}_effort_{args.reasoning_effort}")
        model_dir = args.results_dir / release.release_id / model_slug
        output_paths = [model_dir / f"{_slugify(task.task_id)}--attempt-{args.attempt_index}.json" for task in tasks]
        existing_paths = [path for path in output_paths if path.exists()]
        if existing_paths:
            raise SystemExit(
                "Recorded result artifacts are immutable; refusing to overwrite "
                f"{len(existing_paths)} existing file(s), beginning with {existing_paths[0]}. "
                "Use a new results directory or model revision label."
            )
        for task, output_path in zip(tasks, output_paths, strict=True):
            result = run_trial(task, adapter, seed=None, temperature=None, max_tokens=None)
            payload = {**result.to_dict(), "status": "completed", "attempt_index": args.attempt_index - 1}
            _write_json_exclusive(output_path, payload)
        print(json.dumps({"model": adapter.model_descriptor().model_name, "task_count": len(tasks)}, sort_keys=True))
        return


def _build_adapter(
    adapter: str,
    model_name: str,
    base_url: str,
    timeout: int,
    *,
    seed: int,
    temperature: float,
    max_tokens: int,
    max_rate_limit_retries: int = 8,
    send_temperature: bool = True,
    send_seed: bool = True,
    completion_limit_field: str = "max_completion_tokens",
    response_format_dialect: str = "openai",
    send_reasoning_effort: bool = True,
    api_key_env: str | None = None,
    provider: str | None = None,
    response_format: str = "json_schema",
    strict_schema: bool = True,
    reasoning_effort: str | None = None,
    reasoning_format: str | None = None,
    ollama_keep_alive: str | int | None = 0,
    ollama_num_ctx: int = 4096,
    model_revision_override: str | None = None,
) -> AgentAdapter:
    if not 0 <= max_rate_limit_retries <= 20:
        raise ValueError("--max-rate-limit-retries must be between 0 and 20.")
    if adapter == "ollama":
        if (
            not send_temperature
            or not send_seed
            or completion_limit_field != "max_completion_tokens"
            or response_format_dialect != "openai"
            or not send_reasoning_effort
            or reasoning_format is not None
        ):
            raise ValueError("OpenAI request dialect options cannot be used with the Ollama adapter.")
        return OllamaAdapter(
            model_name=model_name,
            base_url=base_url or "http://127.0.0.1:11434",
            timeout_seconds=timeout,
            seed=seed,
            temperature=temperature,
            max_tokens=max_tokens,
            keep_alive=ollama_keep_alive,
            context_window=ollama_num_ctx,
            model_revision_override=model_revision_override,
        )
    presets = {
        "groq": ("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY"),
        "openai": ("openai", "https://api.openai.com/v1", "OPENAI_API_KEY"),
    }
    if adapter in presets:
        default_provider, default_base_url, default_key_env = presets[adapter]
    elif adapter == "openai-compatible":
        default_provider, default_base_url, default_key_env = (
            "openai-compatible",
            "",
            "OPENAI_COMPATIBLE_API_KEY",
        )
    else:
        raise ValueError(f"Unsupported adapter {adapter!r}.")
    resolved_base_url = base_url or default_base_url
    if not resolved_base_url:
        raise ValueError("--base-url is required for the openai-compatible adapter.")
    key_env = api_key_env or default_key_env
    api_key = os.environ.get(key_env, "")
    if not api_key:
        raise ValueError(f"Provider credential environment variable {key_env!r} is not set.")
    return OpenAICompatibleAdapter(
        model_name=model_name,
        api_key=api_key,
        base_url=resolved_base_url,
        provider=provider or default_provider,
        temperature=temperature,
        seed=seed,
        max_tokens=max_tokens,
        timeout_seconds=timeout,
        response_format=response_format,
        strict_schema=strict_schema,
        reasoning_effort=reasoning_effort,
        reasoning_format=reasoning_format,
        max_rate_limit_retries=max_rate_limit_retries,
        send_temperature=send_temperature,
        send_seed=send_seed,
        completion_limit_field=completion_limit_field,
        response_format_dialect=response_format_dialect,
        send_reasoning_effort=send_reasoning_effort,
        model_revision_override=model_revision_override,
    )


def _resolve_model_revision(
    adapter: str,
    model_name: str,
    revision_override: str | None,
    base_url: str | None,
    timeout: int,
) -> str | None:
    if revision_override:
        return revision_override
    if adapter != "ollama":
        return None
    try:
        return resolve_ollama_model_revision(
            model_name,
            base_url=base_url or "http://127.0.0.1:11434",
            timeout_seconds=timeout,
        )
    except AdapterError as error:
        raise SystemExit(f"Cannot freeze the Ollama model identity for {model_name!r}: {error}") from error


def _slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_").lower()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_json_exclusive(path: Path, payload: dict[str, object]) -> None:
    """Create an immutable result artifact without replacing an existing run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _parse_route_receipt_bindings(values: list[str]) -> dict[str, Path]:
    bindings: dict[str, Path] = {}
    for value in values:
        route_id, separator, path = value.partition("=")
        if not separator or not route_id or not path:
            raise RouteQualificationError("--receipt must use ROUTE_ID=PATH syntax.")
        if route_id in bindings:
            raise RouteQualificationError(f"Duplicate receipt binding for route {route_id!r}.")
        bindings[route_id] = Path(path)
    return bindings


def _validate_resumable_attempt(
    path: Path,
    *,
    task: TaskSpec,
    model_descriptor: ModelDescriptor,
    adapter_settings: dict[str, object],
    attempt_index: int,
    seed: int,
    temperature: float,
    max_tokens: int,
) -> None:
    """Prove that an immutable checkpoint belongs to the requested campaign."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Cannot resume from unreadable result artifact {path}: {error}") from error
    if not isinstance(payload, dict):
        raise SystemExit(f"Cannot resume: result artifact {path} must contain a JSON object.")

    manifest = payload.get("manifest")
    if not isinstance(manifest, dict):
        raise SystemExit(f"Cannot resume: result artifact {path} has no run manifest.")
    expected = {
        "schema_version": "medeval.run.v2",
        "task_id": task.task_id,
        "task_version": task.version,
        "model": asdict(model_descriptor),
        "adapter_settings": adapter_settings,
        "adapter_settings_hash": stable_hash(adapter_settings),
        "seed": seed,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "prompt_hash": prompt_hash_for_task(task),
        "tool_schema_hash": tool_schema_hash_for_task(task),
        "system_prompt_hash": system_prompt_hash(),
        "runtime_task_hash": runtime_task_hash_for_task(task),
        "grader_hash": grader_hash_for_task(task),
        "scoring_revision": SCORING_REVISION,
    }
    mismatches = [key for key, value in expected.items() if manifest.get(key) != value]
    if payload.get("attempt_index") != attempt_index:
        mismatches.append("attempt_index")
    if payload.get("status") not in {"completed", "error"}:
        mismatches.append("status")
    if not isinstance(manifest.get("run_id"), str) or not manifest["run_id"].strip():
        mismatches.append("run_id")
    if mismatches:
        raise SystemExit(
            f"Cannot resume: immutable result artifact {path} does not match the requested "
            f"campaign contract ({', '.join(sorted(set(mismatches)))})."
        )

    if payload.get("status") == "completed":
        output = payload.get("output")
        if not isinstance(output, dict):
            raise SystemExit(f"Cannot resume: completed result artifact {path} has no JSON output object.")
        grades = score_attempt(task, output)
        expected_grades = [grade.to_dict() for grade in grades]
        stored_score = payload.get("score")
        score_matches = (
            isinstance(stored_score, (int, float))
            and not isinstance(stored_score, bool)
            and abs(float(stored_score) - weighted_grade_score(grades)) <= 1e-12
        )
        if (
            payload.get("grades") != expected_grades
            or payload.get("passed") is not grades_pass(grades)
            or payload.get("safe") is not grades_safe(grades)
            or not score_matches
        ):
            raise SystemExit(f"Cannot resume: completed result artifact {path} disagrees with deterministic regrading.")
    else:
        raise SystemExit(
            f"Cannot resume: legacy transport-error artifact {path} occupies an immutable attempt key. "
            "Use a new results directory for this campaign. Current runners store transport failures "
            "in an append-only side ledger so the canonical attempt remains resumable."
        )


if __name__ == "__main__":
    main()
