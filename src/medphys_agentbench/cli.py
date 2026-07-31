"""CLI for validating tasks, running single trials, and producing leaderboard summaries."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from .adapters.ollama import OllamaAdapter
from .adapters.reference import DevelopmentReferenceAgent
from .release_loader import load_release
from .reporting import summarize_release, write_summary
from .runner import run_trial
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

    run = subparsers.add_parser("run", help="Run a single task against an adapter/model pair.")
    run.add_argument("task_file", type=Path)
    run.add_argument("--adapter", choices=["ollama"], required=True)
    run.add_argument("--model", required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--base-url", default="http://127.0.0.1:11434")
    run.add_argument("--timeout", type=int, default=300)
    run.add_argument("--seed", type=int, default=20260731)
    run.add_argument("--temperature", type=float, default=0.0)
    run.add_argument("--max-tokens", type=int, default=1024)

    run_release = subparsers.add_parser("run-release", help="Run every task in a release for one or more models.")
    run_release.add_argument("release_file", type=Path)
    run_release.add_argument("--adapter", choices=["ollama"], required=True)
    run_release.add_argument("--model", action="append", required=True)
    run_release.add_argument("--results-dir", type=Path, default=Path("runs"))
    run_release.add_argument("--attempts", type=int, default=1)
    run_release.add_argument("--base-url", default="http://127.0.0.1:11434")
    run_release.add_argument("--timeout", type=int, default=300)
    run_release.add_argument("--seed", type=int, default=20260731)
    run_release.add_argument("--temperature", type=float, default=0.0)
    run_release.add_argument("--max-tokens", type=int, default=1024)
    run_release.add_argument("--fail-fast", action="store_true")

    summarize = subparsers.add_parser("summarize", help="Build leaderboard JSON from a completed release run.")
    summarize.add_argument("release_file", type=Path)
    summarize.add_argument("--results-dir", type=Path, default=Path("runs"))
    summarize.add_argument("--output", type=Path, required=True)

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
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
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
                    "task_count": len(tasks),
                    "task_ids": [task.task_id for task in tasks],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    if args.command == "run":
        task = load_task(args.task_file)
        adapter = _build_adapter(args.adapter, args.model, args.base_url, args.timeout)
        result = run_trial(
            task,
            adapter,
            seed=args.seed,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        _write_json(args.output, result.to_dict())
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        if not result.safe:
            raise SystemExit(1)
        return

    if args.command == "run-release":
        release = load_release(args.release_file)
        tasks = release.load_tasks()
        for model_name in args.model:
            adapter = _build_adapter(args.adapter, model_name, args.base_url, args.timeout)
            model_slug = _slugify(model_name)
            model_dir = args.results_dir / release.release_id / model_slug
            model_dir.mkdir(parents=True, exist_ok=True)
            for task in tasks:
                for attempt_index in range(args.attempts):
                    run_id = str(uuid4())
                    output_path = model_dir / (
                        f"{_slugify(task.task_id)}--attempt-{attempt_index + 1}.json"
                    )
                    try:
                        result = run_trial(
                            task,
                            adapter,
                            seed=args.seed + attempt_index,
                            temperature=args.temperature,
                            max_tokens=args.max_tokens,
                            run_id=run_id,
                        )
                        payload = {
                            **result.to_dict(),
                            "status": "completed",
                            "attempt_index": attempt_index,
                        }
                    except Exception as error:
                        payload = {
                            "status": "error",
                            "attempt_index": attempt_index,
                            "error_type": type(error).__name__,
                            "error": str(error),
                            "passed": False,
                            "safe": False,
                            "score": 0.0,
                            "manifest": {
                                "schema_version": "medeval.run.v1",
                                "run_id": run_id,
                                "task_id": task.task_id,
                                "task_version": task.version,
                                "model": asdict(adapter.model_descriptor()),
                                "seed": args.seed + attempt_index,
                                "temperature": args.temperature,
                                "max_tokens": args.max_tokens,
                            },
                            "output": {},
                            "grades": [],
                            "trace": [],
                            "raw_response": {},
                            "duration_seconds": 0.0,
                        }
                        if args.fail_fast:
                            _write_json(output_path, payload)
                            raise
                    _write_json(output_path, payload)
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
        return

    if args.command == "summarize":
        release = load_release(args.release_file)
        summary = summarize_release(release, args.results_dir)
        write_summary(summary, args.output)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return


def _build_adapter(
    adapter: str,
    model_name: str,
    base_url: str,
    timeout: int,
) -> OllamaAdapter:
    if adapter == "ollama":
        return OllamaAdapter(
            model_name=model_name,
            base_url=base_url,
            timeout_seconds=timeout,
        )
    raise ValueError(f"Unsupported adapter {adapter!r}.")


def _slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_").lower()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()
