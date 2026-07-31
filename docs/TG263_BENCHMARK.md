# TG-263 structure-naming benchmark slice

## Status and scope

This public slice evaluates whether an agent can apply a small, independently
authored set of TG-263-style naming rules to synthetic structure records. It is
a research benchmark, not a clinical terminology service or RT Structure Set
editor. No task connects to a treatment-planning system, contains patient data,
or authorizes a clinical rename.

The implementation has two intentionally separate layers:

- `src/medphys_agentbench/tg263.py` provides deterministic syntax checks,
  conservative normalization, ambiguity refusal, and case-insensitive collision
  detection.
- `tasks/public/structure_naming/` contains standalone public tasks whose gold
  outcomes are encoded in deterministic graders and hidden from runtime task
  projections by the existing benchmark contract.

## Source and licensing boundary

The normative source is AAPM Task Group 263, *Standardizing Nomenclatures in
Radiation Oncology* (2018), plus the official supplemental landing page:

- [AAPM TG-263 report](https://www.aapm.org/pubs/reports/RPT_263.pdf)
- [AAPM TG-263 supplemental materials](https://www.aapm.org/pubs/reports/RPT_263_Supplemental/)
- [AAPM terms of use](https://www.aapm.org/terms.asp)

The official nomenclature worksheet is not copied into this repository. AAPM's
terms restrict reproduction of site materials, so the code and fixtures use a
small independently authored vocabulary and paraphrased general rules. The
benchmark fixtures themselves are synthetic and licensed CC0-1.0. That license
does not apply to the AAPM report or supplemental files.

TG-263 Update 1 remains an active AAPM task group as of 2026-07-31; this slice
does not treat a survey or draft activity as a normative replacement for the
2018 report. A future published update should trigger a new task version and a
documented migration rather than silently changing existing gold labels.

## Implemented rule contract

The public rule engine implements the following general behavior:

- non-target names contain no spaces, use `_` as a separator, and are limited
  to 16 characters;
- paired-organ laterality is a terminal `_L` or `_R` suffix;
- `_PRV` and an optional zero-padded millimetre margin precede laterality, for
  example `OpticNrv_PRV03_L`;
- `~` marks a partial structure, `^Qualifier` is terminal, and `z` is the
  benchmark's optimization-only prefix;
- target names use an open grammar beginning with GTV, CTV, ITV, IGTV, ICTV,
  PTV, or PTV! and are not treated as members of a closed worksheet list;
- PTV! is preserved only when `segmented_volume: true` explicitly confirms its
  semantics;
- names must be unique under Unicode `casefold()` comparison; all colliding
  records escalate and retain the proposed name for review;
- unknown structures, absent required laterality, contradictory context, and
  invalid margins escalate. The engine never invents a numeric suffix or makes
  an approximate anatomical match.

Accepted record keys are:

| Key | Meaning |
| --- | --- |
| `source_name` | Required source label. |
| `roi_number` | Optional stable synthetic record identifier. |
| `structure_class` | `auto`, `non_target`, or `target`. |
| `laterality` | Optional `L`, `R`, `left`, or `right`. |
| `is_prv` / `prv_margin_mm` | Explicit PRV state and integer margin from 0 through 99 mm. |
| `partial` | Explicit partial-structure flag. |
| `custom_qualifier` | Short alphanumeric terminal qualifier. |
| `optimization` | Applies the benchmark's `z` prefix. |
| `segmented_volume` | Required as `true` to confirm PTV! semantics. |

The engine returns `keep`, `rename`, or `escalate`, a proposed canonical name
when one is safely available, and machine-readable reason codes. It does not
mutate its input.

## Task matrix

The 18 public cases are selected to cover ordinary, boundary, ambiguous, and
metamorphic behavior:

| Case | Expected behavior |
| --- | --- |
| Already conformant Brainstem | Keep |
| Left parotid alias | Rename to `Parotid_L` |
| Parotid without laterality | Escalate |
| Contradictory name/context laterality | Escalate |
| Bilateral kidney collective | Rename to `Kidneys` |
| Spinal cord PRV, 5 mm | Rename to `SpinalCord_PRV05` |
| Left optic nerve PRV, 3 mm | Rename to `OpticNrv_PRV03_L` |
| PRV with no supplied margin | Keep `_PRV`; do not invent a margin |
| Partial right lung | Rename to `Lung~_R` |
| Custom qualifier | Rename to `Lungs^Ex` |
| Target modality/dose grammar | Keep `PTVp1_CT1_7000` |
| Target fractionation grammar | Keep `PTV_Liver_20Gyx3` |
| Unconfirmed PTV! semantics | Escalate |
| Confirmed PTV! semantics | Keep |
| Case-insensitive canonical collision | Escalate all colliding records |
| Unknown anatomy | Escalate |
| Laterality on an unpaired root | Escalate |
| Optimization-only structure | Rename with `z` prefix |

Every task declares an exact output schema and exact or unordered-exact graders
for action, proposed name, reason codes, and escalation. Repository validation
constructs a reference output from those declared graders and proves that each
task's own deterministic graders accept it. `tests/test_tg263.py` additionally
checks that task gold actions agree with the rule engine.

Metamorphic tests cover:

- input-order invariance when results are keyed by ROI number;
- a laterality context flip producing the corresponding suffix flip;
- two aliases normalizing to the same case-insensitive name producing collision
  escalation rather than arbitrary suffixing;
- source-record immutability.

## DICOM boundary and future mutation track

This initial slice operates on synthetic records, not DICOM files. A future
RTSTRUCT mutation track should use synthetic DICOM instances and deterministically
verify all of the following before it is eligible for scoring:

1. Only `StructureSetROISequence[*].ROIName` values intended by the reference
   mapping changed.
2. Referenced ROI numbers still join correctly across Structure Set ROI, ROI
   Contour, and RT ROI Observations sequences.
3. Contour coordinates, frame-of-reference references, observation attributes,
   SOP Instance UID policy, and approval state follow an explicit versioned
   mutation contract.
4. Input and output file hashes, the exact task manifest, and the complete
   rename audit are persisted.
5. Missing context or a collision yields a read-only escalation artifact and no
   modified RTSTRUCT.

Relevant current DICOM modules are the [Structure Set ROI Module](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_c.8.8.5.html),
[ROI Contour Module](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_c.8.8.6.html),
[RT ROI Observations Module](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_c.8.8.8.html),
and [RT Approval Module](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_c.8.8.16.html).

## Comparator tools and non-normative evidence

Open-source projects can inform test ideas but do not define benchmark gold:

- [ESAPIX](https://github.com/rexcardan/ESAPIX) (MIT) includes TG-263-oriented
  regex helpers for name/type checks.
- [StatureTool](https://github.com/tschuler/StatureTool) (Apache-2.0) provides a
  structure-renaming workflow.
- [gacou54/tg263](https://github.com/gacou54/tg263) (MIT) is an ESAPI script with
  stated ESAPIX attribution.
- [RT-Rename](https://github.com/LMUK-RADONC-PHYS-RES/rt-rename) (MIT) explores
  learned RT structure-name harmonization.

Their outputs must be evaluated as candidate behavior, never imported as truth
without independent source and license review.

## Known limitations

- The vocabulary is purposefully small and is not a substitute for the full
  AAPM worksheet.
- Syntax validity does not establish anatomical correctness, contour quality,
  intent, or suitability for dose evaluation.
- The target grammar is intentionally permissive because TG-263 does not define
  one universal institutional target-name sequence.
- The slice does not inspect geometry, DICOM coding sequences, or clinical
  workflow state.
- `casefold()` collision checks are deterministic but do not resolve semantic
  duplicates with different spellings outside the public alias subset.
