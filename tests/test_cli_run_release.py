from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from medphys_agentbench import cli
from medphys_agentbench.adapters.openai_compatible import UnsupportedCapabilityError
from medphys_agentbench.contracts import ModelDescriptor
from medphys_agentbench.release_loader import load_release
from medphys_agentbench.reporting import summarize_release


@dataclass
class _FakeResult:
    passed: bool = True
    safe: bool = True

    def to_dict(self) -> dict[str, object]:
        return {"passed": self.passed, "safe": self.safe}


class _FakeAdapter:
    def __init__(self, model_name: str, seed: int) -> None:
        self.model_name = model_name
        self.seed = seed

    def model_descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(
            provider="fake",
            model_name=self.model_name,
            model_revision=self.model_name,
            harness_name="test-harness",
            harness_revision="test-harness-v1",
        )


def test_run_release_uses_attempt_seed_in_adapter_and_refuses_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter_seeds: list[int] = []
    runner_seeds: list[int] = []

    def fake_build_adapter(*args: object, seed: int, **kwargs: object) -> _FakeAdapter:
        del kwargs
        model_name = str(args[1])
        adapter_seeds.append(seed)
        return _FakeAdapter(model_name, seed)

    def fake_run_trial(*args: object, seed: int, **kwargs: object) -> _FakeResult:
        del kwargs
        adapter = args[1]
        assert isinstance(adapter, _FakeAdapter)
        assert adapter.seed == seed
        runner_seeds.append(seed)
        return _FakeResult()

    monkeypatch.setattr(cli, "_build_adapter", fake_build_adapter)
    monkeypatch.setattr(cli, "run_trial", fake_run_trial)
    command = [
        "medphys-bench",
        "run-release",
        "releases/public_imaging_pilot_v0_4.yaml",
        "--adapter",
        "groq",
        "--model",
        "test-model",
        "--attempts",
        "2",
        "--seed",
        "41",
        "--results-dir",
        str(tmp_path),
    ]
    monkeypatch.setattr(sys, "argv", command)
    cli.main()

    assert set(adapter_seeds) == {41, 42}
    assert adapter_seeds == runner_seeds
    assert len(list(tmp_path.rglob("*.json"))) == 10

    monkeypatch.setattr(sys, "argv", command)
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        cli.main()


def test_run_release_scores_unsupported_required_modality_as_completed_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cli,
        "_build_adapter",
        lambda *args, seed, **_kwargs: _FakeAdapter(str(args[1]), seed),
    )
    monkeypatch.setattr(
        cli,
        "run_trial",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            UnsupportedCapabilityError("required artifact modality unavailable")
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "medphys-bench",
            "run-release",
            "releases/public_imaging_pilot_v0_4.yaml",
            "--adapter",
            "groq",
            "--model",
            "text-only-model",
            "--results-dir",
            str(tmp_path),
        ],
    )

    cli.main()

    artifacts = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(tmp_path.rglob("*.json"))]
    assert all(item["status"] == "completed" for item in artifacts)
    assert all(item["capability_failure"] is True for item in artifacts)
    assert all(item["passed"] is False for item in artifacts)
    summary = summarize_release(load_release("releases/public_imaging_pilot_v0_4.yaml"), tmp_path)
    assert summary["integrity"]["ranked_model_count"] == 1
    assert summary["models"][0]["safe_success_rate"] == 0.0
