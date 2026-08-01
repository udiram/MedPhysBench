# AAPM Task-Group Coverage and Task Derivation

**Status:** scope map, not an AAPM item bank
**Source review:** 2026-07-31

MedPhysBench uses official AAPM report scope pages to identify professional
workflows. It does not copy report tables, numerical tolerances, figures,
worksheets, RAPHEX questions, ABR questions, or answer keys. Public tasks use
independently authored facts, policies, and fixtures; a report link establishes
relevance and the version to consult during expert review.

## Priority radiation-therapy map

| Source | Professional behavior to sample | Original benchmark formulation | Primary grader |
| --- | --- | --- | --- |
| [TG-66: CT simulation QA](https://www.aapm.org/pubs/reports/detail.asp?docid=83) | CT-simulator geometry, image quality, and simulation-process QA | Audit a synthetic CT-sim QA packet and detect geometry/import inconsistencies | Numeric/state checks plus required-evidence set |
| [TG-142: accelerator QA](https://www.aapm.org/pubs/reports/detail.asp?docid=125) and [TG-198 implementation guide](https://www.aapm.org/pubs/reports/detail.asp?docid=215) | Risk-informed routine accelerator QA and implementation | Apply a supplied local policy to trended phantom data; never return equipment to service | Exact flags, trend triggers, escalation |
| [TG-179: CT-based IGRT QA](https://www.aapm.org/pubs/reports/detail.asp?docid=136) | Imaging geometry, registration, and image quality in IGRT | Identify seeded coordinate/calibration defects in a phantom workflow | Geometry tolerance and state graph |
| [TG-284: MR simulation](https://www.aapm.org/pubs/reports/detail.asp?docid=211) | MR simulation geometry, distortion, safety, and workflow evidence | Audit a frozen MR-SIM evidence packet for missing controls | Required-evidence matrix and escalation |
| [TG-132: image registration](https://www.aapm.org/pubs/reports/detail.asp?docid=164) | Registration/fusion validation and uncertainty | Compare known synthetic transforms and catch direction/frame/deformation failures | Landmark/overlap/Jacobian metrics |
| [TG-147: non-radiographic localization](https://aapm.org/pubs/reports/detail.asp?docid=127) | Optical/marker localization QA | Analyze phantom shifts, tracking dropouts, and latency from supplied logs | Numeric deviation and fail-safe state |
| [TG-263: nomenclature](https://www.aapm.org/pubs/reports/detail.asp?docid=171) | Standardized structure/target naming | Collision-aware laterality, alias, qualifier, and unknown-name audit | Exact rename set, collision gate, escalation |
| [TG-106: beam data commissioning](https://www.aapm.org/pubs/reports/detail.asp?docid=106) | Beam-data acquisition and commissioning evidence | Detect setup, detector, normalization, or field-coverage defects in an authored scan set | Units, metadata, curve comparison |
| [TG-157: Monte Carlo beam-model commissioning](https://www.aapm.org/pubs/reports/detail.asp?docid=194) | MC model commissioning and verification | Compare fixed phantom fields against a reference engine with seeded model errors | Dose/profile metrics and uncertainty |
| [MPPG 5.b: TPS dose calculation commissioning](https://www.aapm.org/pubs/MPPG/detail.asp?docid=246) | Commissioning and routine QA of photon/electron dose calculation | Score evidence coverage and independently recalculate authored phantom cases | Coverage matrix plus numeric comparison |
| [TG-219: independent dose/MU verification](https://www.aapm.org/pubs/reports/detail.asp?docid=218) | Independent IMRT/VMAT dose/MU checking | Diagnose disagreements while exposing correlated-input traps | Discrepancy class, magnitude, escalation |
| [TG-218: measurement-based IMRT QA](https://www.aapm.org/pubs/reports/detail.asp?docid=173) | Measurement methods and tolerance/action interpretation | Apply a supplied QA policy to synthetic planar/3D measurements | Gamma/metric calculation and policy state |
| [TG-307: EPID IMRT/VMAT QA](https://www.aapm.org/pubs/reports/detail.asp?docid=278) | EPID-based patient-specific QA | Localize seeded MLC/small-field defects in research EPID data | Known-defect detection and calibrated false alarms |
| [TG-186: model-based brachytherapy dose](https://www.aapm.org/pubs/reports/detail.asp?docid=138) | Heterogeneity-aware brachytherapy dose methods | Compare an authored MBDCA case with a TG-43-style baseline and identify assumption failures | Dose metric deltas and material audit |
| [WG-DCAB 372: brachytherapy MBDCA commissioning](https://aapm.org/pubs/reports/detail.asp?docid=272) | Commissioning test cases and workflow evidence | Execute a frozen commissioning suite and detect source/material/artifact mismatch | Exact evidence ledger and numeric checks |
| [MPPG 11.a: plan and chart review](https://www.aapm.org/pubs/MPPG/detail.asp?docid=263) | Risk-prioritized plan/chart review | Find seeded prescription, structure, dose, transfer, and authorization inconsistencies | Defect capture, false alarms, time, escalation |
| [TG-288: incident narratives](https://www.aapm.org/pubs/reports/detail.asp?docid=286) | Complete, learning-oriented incident narratives | Convert fictional event evidence to a structured, non-blaming report without PHI | Required fields, chronology, attribution/PHI gates |

The broader lifecycle map, including TG-100, TG-201, TG-262, TG-275, TG-302,
TG-314, and specialty overlays, is in [RT_COMPETENCY_MAP.md](RT_COMPETENCY_MAP.md).

## Current implementation status

| Lane | Implemented public evidence | What remains before a strong comparison claim |
| --- | --- | --- |
| TG-263 | 18 collision/ambiguity tasks plus two-patient OpenKBP paired-parotid naming audits | Independent physicist review, wider anatomy and institution-level adversarial renames |
| Planning review | Two OpenKBP plan-criteria audits with deterministic DVH-derived metrics and missing-structure handling | More independent patient families, plan perturbations, human baseline, cross-engine metrics |
| Image/structure review | Two bilateral-parotid grid segmentation tasks and two dose-region tasks | Full-volume/surface metrics, more sites/modalities, blinded cases, expert contour variability |
| Plan-data integrity | Two OpenKBP structure-inventory audits | DICOM-RT graph/UID/coordinate variants and planner round trips |
| Machine/IGRT/TPS/PSQA/brachy/incident | Taxonomy and existing core author-created calculations only | Executable fixtures, negative controls, reviewers, declared source versions |

The v0.6 pilot therefore samples two patient families, not “all of radiation
therapy.” Its value is the frozen harness and auditable task pattern; its main
limitation is external validity.

## ABR and RAPHEX boundary

ABR and RAPHEX material can inform a domain blueprint only through material that
is explicitly public and permitted for reuse. The benchmark must never scrape,
transcribe, reconstruct, solicit, or redistribute recalled examination content,
secure candidate material, paid question banks, or answer keys. Knowledge tasks
should instead be independently written from textbooks, peer-reviewed articles,
public regulations, and official report scope, then reviewed for correctness and
for inadvertent similarity to protected items.

Any future “board-style” lane must publish:

- an author declaration that no recalled/protected exam item was used;
- source citations for every factual claim and independently derived solution;
- similarity screening against the repository's own public tasks;
- at least two qualified reviewer approvals;
- a contamination label acknowledging likely general medical-physics training
  exposure even when the exact task is original.
