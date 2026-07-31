"""Conservative, independently authored TG-263 naming helpers.

This module implements a small public benchmark vocabulary and the general
naming grammar described by AAPM TG-263.  It is not a copy of the copyrighted
TG-263 nomenclature worksheet and is not a complete clinical terminology
service.  Unknown or contradictory inputs are deliberately escalated.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from typing import Any


class StructureAction(StrEnum):
    """Allowed outcomes for a proposed structure-name change."""

    KEEP = "keep"
    RENAME = "rename"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class NameValidation:
    """Deterministic syntax result for one proposed name."""

    valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True)
class StructureDecision:
    """Conservative normalization decision for one source structure."""

    source_name: str
    action: StructureAction
    canonical_name: str | None
    reason_codes: tuple[str, ...]
    roi_number: int | str | None = None

    @property
    def requires_escalation(self) -> bool:
        return self.action is StructureAction.ESCALATE

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["action"] = self.action.value
        payload["requires_escalation"] = self.requires_escalation
        return payload


# A small, independently authored benchmark vocabulary.  It intentionally
# covers only the public examples exercised by this benchmark slice.
_ALIASES: dict[str, str] = {
    "brainstem": "Brainstem",
    "brainstemorgan": "Brainstem",
    "spinalcord": "SpinalCord",
    "cord": "SpinalCord",
    "parotid": "Parotid",
    "parotidgland": "Parotid",
    "kidney": "Kidney",
    "kidneys": "Kidneys",
    "lung": "Lung",
    "lungs": "Lungs",
    "opticnerve": "OpticNrv",
    "opticnrv": "OpticNrv",
    "opticchiasm": "OpticChiasm",
    "chiasm": "OpticChiasm",
    "cochlea": "Cochlea",
    "bowelbag": "Bowel_Bag",
    "brachialplexus": "BrachialPlex",
    "femoralhead": "Femur_Head",
}

_PAIRED_ROOTS = frozenset({"Parotid", "Kidney", "Lung", "OpticNrv", "Cochlea", "BrachialPlex", "Femur_Head"})
_TARGET_PREFIX = re.compile(r"^(?:GTV|CTV|ITV|IGTV|ICTV|PTV!?)", re.IGNORECASE)
_TARGET_NAME = re.compile(
    r"^(?:GTV|CTV|ITV|IGTV|ICTV|PTV!?)(?:(?:par|vas|sb|[npsbv])\d*)?"
    r"(?:_[A-Za-z0-9~!-]+)*(?:\^[A-Za-z0-9]+)?$"
)
_ALLOWED_NAME = re.compile(r"^[A-Za-z0-9_~^!-]+$")
_PRV_SUFFIX = re.compile(r"_PRV(?P<margin>\d{1,2})?(?:_[LR])?(?:\^[A-Za-z0-9]+)?$")


def validate_tg263_name(name: str, *, structure_class: str = "non_target") -> NameValidation:
    """Validate general TG-263 syntax without asserting worksheet membership.

    ``structure_class`` is either ``"non_target"`` or ``"target"``.  Target
    names use an open grammar and are not subject to the 16-character limit.
    """

    errors: list[str] = []
    if not isinstance(name, str) or not name:
        return NameValidation(False, ("empty_name",))
    if structure_class not in {"non_target", "target"}:
        raise ValueError("structure_class must be 'non_target' or 'target'")
    if any(character.isspace() for character in name):
        errors.append("whitespace_not_allowed")
    if not _ALLOWED_NAME.fullmatch(name):
        errors.append("invalid_character")

    if structure_class == "target":
        if not _TARGET_NAME.fullmatch(name):
            errors.append("invalid_target_grammar")
    else:
        if len(name) > 16:
            errors.append("non_target_name_over_16_characters")
        if _TARGET_PREFIX.match(name):
            errors.append("target_name_misclassified")

    if re.search(r"_(?:L|R)_PRV", name):
        errors.append("prv_must_precede_laterality")
    if "_PRV" in name:
        match = _PRV_SUFFIX.search(name)
        if not match:
            errors.append("invalid_prv_suffix")
        elif (margin := match.group("margin")) and len(margin) == 1 and len(name) < 16:
            errors.append("single_digit_prv_margin_without_length_constraint")

    return NameValidation(not errors, tuple(dict.fromkeys(errors)))


def normalize_structure(record: Mapping[str, Any]) -> StructureDecision:
    """Return a conservative TG-263 decision for a synthetic structure record.

    Accepted context keys are documented in ``docs/TG263_BENCHMARK.md``.  The
    input mapping is never mutated.  Missing information and contradictions
    produce ``escalate`` rather than a guessed name.
    """

    source_name = str(record.get("source_name", ""))
    roi_number = record.get("roi_number")
    structure_class = str(record.get("structure_class", "auto"))
    if structure_class not in {"auto", "non_target", "target"}:
        return _escalate(source_name, roi_number, "invalid_structure_class")

    is_target = structure_class == "target" or (structure_class == "auto" and bool(_TARGET_PREFIX.match(source_name)))
    if is_target:
        return _normalize_target(record, source_name, roi_number)

    parsed_source, side_from_name, source_flags = _parse_source(source_name)
    if side_from_name == "conflict":
        return _escalate(source_name, roi_number, "contradictory_laterality")
    explicit_side = _normalize_laterality(record.get("laterality"))
    if explicit_side == "invalid":
        return _escalate(source_name, roi_number, "invalid_laterality")
    if side_from_name and explicit_side and side_from_name != explicit_side:
        return _escalate(source_name, roi_number, "contradictory_laterality")
    side = explicit_side or side_from_name

    root = _ALIASES.get(parsed_source)
    if root is None:
        return _escalate(source_name, roi_number, "unknown_structure")
    if root in _PAIRED_ROOTS and side is None:
        return _escalate(source_name, roi_number, "missing_laterality")
    if root not in _PAIRED_ROOTS and side is not None:
        return _escalate(source_name, roi_number, "unexpected_laterality")

    partial = bool(record.get("partial", source_flags["partial"]))
    is_prv = bool(record.get("is_prv", source_flags["is_prv"]))
    margin = record.get("prv_margin_mm", source_flags["prv_margin_mm"])
    if margin is not None and not is_prv:
        return _escalate(source_name, roi_number, "prv_margin_without_prv")
    if margin is not None:
        if isinstance(margin, bool) or not isinstance(margin, int) or not 0 <= margin <= 99:
            return _escalate(source_name, roi_number, "invalid_prv_margin")

    qualifier = record.get("custom_qualifier")
    if qualifier is not None and not re.fullmatch(r"[A-Za-z0-9]+", str(qualifier)):
        return _escalate(source_name, roi_number, "invalid_custom_qualifier")

    canonical = root
    if partial:
        canonical += "~"
    if is_prv:
        canonical += "_PRV"
        if margin is not None:
            canonical += f"{margin:02d}"
    if side in {"L", "R"}:
        canonical += f"_{side}"
    if qualifier is not None:
        canonical += f"^{qualifier}"
    if bool(record.get("optimization", False)):
        canonical = f"z{canonical}"

    validation = validate_tg263_name(canonical)
    if not validation.valid:
        return StructureDecision(
            source_name,
            StructureAction.ESCALATE,
            canonical,
            validation.errors,
            roi_number,
        )

    action = StructureAction.KEEP if source_name == canonical else StructureAction.RENAME
    reasons = ("already_conformant",) if action is StructureAction.KEEP else ("deterministic_normalization",)
    return StructureDecision(source_name, action, canonical, reasons, roi_number)


def normalize_structure_set(records: Iterable[Mapping[str, Any]]) -> tuple[StructureDecision, ...]:
    """Normalize records and escalate every case-insensitive name collision."""

    decisions = [normalize_structure(record) for record in records]
    by_name: dict[str, list[int]] = {}
    for index, decision in enumerate(decisions):
        if decision.canonical_name is not None:
            by_name.setdefault(decision.canonical_name.casefold(), []).append(index)
    for indexes in by_name.values():
        if len(indexes) < 2:
            continue
        for index in indexes:
            decision = decisions[index]
            decisions[index] = replace(
                decision,
                action=StructureAction.ESCALATE,
                reason_codes=tuple(dict.fromkeys((*decision.reason_codes, "case_insensitive_collision"))),
            )
    return tuple(decisions)


def _normalize_target(record: Mapping[str, Any], source_name: str, roi_number: int | str | None) -> StructureDecision:
    validation = validate_tg263_name(source_name, structure_class="target")
    if not validation.valid:
        return StructureDecision(source_name, StructureAction.ESCALATE, None, validation.errors, roi_number)
    if source_name.startswith("PTV!") and record.get("segmented_volume") is not True:
        return _escalate(source_name, roi_number, "ptv_bang_semantics_unconfirmed")
    return StructureDecision(
        source_name,
        StructureAction.KEEP,
        source_name,
        ("valid_target_grammar",),
        roi_number,
    )


def _parse_source(name: str) -> tuple[str, str | None, dict[str, Any]]:
    working = name.strip()
    side: str | None = None
    left = bool(re.search(r"(?:^|[\s_-])left(?:$|[\s_-])|(?:^|_)L$", working, re.IGNORECASE))
    right = bool(re.search(r"(?:^|[\s_-])right(?:$|[\s_-])|(?:^|_)R$", working, re.IGNORECASE))
    if left and right:
        side = "conflict"
    elif left:
        side = "L"
    elif right:
        side = "R"

    partial = "~" in working
    prv_match = re.search(r"(?:[\s_-])PRV(?:[\s_-]?(\d{1,2}))?(?:\s*mm)?", working, re.IGNORECASE)
    is_prv = prv_match is not None
    prv_margin = int(prv_match.group(1)) if prv_match and prv_match.group(1) else None

    working = re.sub(r"(?:^|[\s_-])(?:left|right)(?=$|[\s_-])", " ", working, flags=re.IGNORECASE)
    working = re.sub(r"_(?:L|R)$", "", working, flags=re.IGNORECASE)
    working = re.sub(r"(?:[\s_-])PRV(?:[\s_-]?\d{1,2})?(?:\s*mm)?", " ", working, flags=re.IGNORECASE)
    working = working.replace("~", "")
    lexical_key = re.sub(r"[^A-Za-z0-9]", "", working).casefold()
    return lexical_key, side, {"partial": partial, "is_prv": is_prv, "prv_margin_mm": prv_margin}


def _normalize_laterality(value: Any) -> str | None:
    if value is None or value == "":
        return None
    normalized = str(value).strip().casefold()
    if normalized in {"l", "left"}:
        return "L"
    if normalized in {"r", "right"}:
        return "R"
    return "invalid"


def _escalate(source_name: str, roi_number: int | str | None, reason: str) -> StructureDecision:
    return StructureDecision(source_name, StructureAction.ESCALATE, None, (reason,), roi_number)
