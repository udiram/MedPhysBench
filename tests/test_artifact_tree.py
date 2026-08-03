from __future__ import annotations

from pathlib import Path

import pytest

from medphys_agentbench.artifact_tree import artifact_tree_sha256, json_artifact_inventory


def test_json_artifact_inventory_is_stable_and_classifies_transport_errors(tmp_path: Path) -> None:
    (tmp_path / "b.json").write_text('{"value":2}\n', encoding="utf-8")
    (tmp_path / "a.json").write_text('{"value":1}\n', encoding="utf-8")
    transport = tmp_path / "_transport_errors"
    transport.mkdir()
    (transport / "failure.json").write_text('{"kind":"quota"}\n', encoding="utf-8")

    inventory = json_artifact_inventory(tmp_path)

    assert [item["path"] for item in inventory] == [
        "_transport_errors/failure.json",
        "a.json",
        "b.json",
    ]
    assert [item["kind"] for item in inventory] == ["transport_error", "result", "result"]
    assert all(len(item["sha256"]) == 64 and item["bytes"] > 1 for item in inventory)
    assert artifact_tree_sha256(inventory) == artifact_tree_sha256(json_artifact_inventory(tmp_path))


def test_artifact_tree_hash_changes_when_file_bytes_change(tmp_path: Path) -> None:
    artifact = tmp_path / "attempt.json"
    artifact.write_text('{"score":0}\n', encoding="utf-8")
    original = artifact_tree_sha256(json_artifact_inventory(tmp_path))

    artifact.write_text('{"score":1}\n', encoding="utf-8")

    assert artifact_tree_sha256(json_artifact_inventory(tmp_path)) != original


def test_json_artifact_inventory_rejects_empty_non_json_and_symlink_inputs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="empty"):
        json_artifact_inventory(tmp_path)

    non_json = tmp_path / "notes.txt"
    non_json.write_text("not an artifact", encoding="utf-8")
    with pytest.raises(ValueError, match="Only JSON"):
        json_artifact_inventory(tmp_path)
    non_json.unlink()

    target = tmp_path / "target.json"
    target.write_text("{}\n", encoding="utf-8")
    link = tmp_path / "linked.json"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="symbolic links"):
        json_artifact_inventory(tmp_path)
