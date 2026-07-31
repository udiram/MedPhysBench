# Radiation-Therapy Competency Map

**Status:** original benchmark taxonomy; research-only and non-clinical
**Source review date:** 2026-07-31

This map turns the radiation-therapy workflow into independently gradeable
assistance competencies. It uses official AAPM Task Group (TG) and Medical
Physics Practice Guideline (MPPG) public scope summaries as anchors. It does not
copy or reconstruct AAPM report tables, recommended checklists, numerical
tolerances, proprietary figures, exam questions, or institution-specific policy.

AAPM describes MPPGs as minimum-practice guidance rather than replacements for
detailed TG reports, and notes that individual care still requires independent
clinical judgment; see the official [MPPG program scope](https://www.aapm.org/pubs/MPPG/).
The current [MPPG 10.b scope-of-practice summary](https://www.aapm.org/pubs/mppg/detail.asp?docid=305)
also spans administrative, clinical, educational, informatics, equipment,
quality, and safety work. MedPhysBench uses those categories to check coverage,
not to certify a person or model as a Qualified Medical Physicist (QMP).

## 1. Competency dimensions

Every RT task receives one lifecycle phase and at least one competency dimension:

| Dimension | Gradeable behavior | Not inferred |
| --- | --- | --- |
| Physics calculation | Correct units, formula, assumptions, tolerance application, and uncertainty from supplied inputs | Ability to commission or calibrate clinical equipment |
| Artifact integrity | Detect mismatch or incompleteness across synthetic images, structures, plan, dose, record, and logs | Clinical meaning of patient anatomy or prescription |
| Evidence grounding | Retrieve and apply the correct supplied revision with traceable source identifiers | Permission to reproduce an external standard |
| Workflow state | Reach the correct state in a mock service with minimal authorized actions | Interoperability with a real TPS/OIS/linac |
| Independent verification | Compare separately generated evidence, identify correlated assumptions, and state residual uncertainty | That two agreeing software systems are clinically correct |
| Risk and escalation | Identify a qualified-human decision boundary, stop unsafe action, and provide a useful handoff | Autonomous approval or clinical responsibility |
| Robustness | Preserve or correctly change the decision under controlled counterfactuals | Generalization to every site, vendor, modality, or patient |
| Quality communication | Produce a factual, structured, non-authorizing report | Clinical sign-off or legal documentation |

## 2. End-to-end RT workflow coverage

The table maps source **themes** to original task formulations. A linked report is
a scientific/scope reference, not a redistributable item bank. Authors must use
the source policy in [KNOWLEDGE_SOURCE_POLICY.md](KNOWLEDGE_SOURCE_POLICY.md).

| Workflow phase | Benchmark competency | Safe task and preferred evidence | Difficulty / risk | Public scope anchors |
| --- | --- | --- | --- | --- |
| 1. Program design and quality management | Build a process map; identify failure modes, controls, ownership, and residual risk from a synthetic workflow | Complete a supplied FMEA/fault-tree fragment or identify missing control; deterministic fields plus SME rubric | D1–D3 / risk 1–2 | [TG-100](https://aapm.org/pubs/reports/detail.asp?docid=156) frames risk analysis across planning and delivery; [MPPG 4.b](https://www.aapm.org/pubs/MPPG/detail.asp?docid=265) covers checklist lifecycle |
| 2. Procurement, acceptance, and independent validation | Distinguish vendor evidence from independent verification; design a bounded acceptance evidence matrix | Compare synthetic vendor claims, measurement records, and unresolved tests; no equipment approval | D2–D4 / risk 2–3 escalation | [TG-332](https://www.aapm.org/pubs/reports/detail.asp?docid=298) addresses independent validation of vendor-provided and black-box systems; [MPPG 15.A](https://www.aapm.org/pubs/mppg/detail.asp?docid=273) anchors peer review |
| 3. Reference dosimetry and beam-data commissioning | Recompute supplied corrections/uncertainty; detect setup, unit, or detector/data inconsistencies | Author-created numeric fixture with explicit constants and tolerance; no real machine output calibration | D1–D3 / risk 1–2 | [TG-51 implementation guidance](https://www.aapm.org/pubs/reports/detail.asp?docid=227), [current electron addendum](https://www.aapm.org/pubs/reports/detail.asp?docid=284), and [TG-106](https://www.aapm.org/pubs/reports/detail.asp?docid=106) |
| 4. Treatment-unit baseline and routine performance | Interpret frozen QA results against a provided local policy; identify maintenance/change consequences | Trend table, measurement metadata, and predeclared action bands; output is flag/handoff, never return-to-service | D1–D3 / risk 2–3 escalation | [MPPG 8.b](https://www.aapm.org/pubs/reports/detail.asp?docid=274) covers linac performance tests selected for clinical use; [TG-198/TG-142 implementation listing](https://www.aapm.org/pubs/reports/?s=linear+accelerator) |
| 5. Simulation, immobilization, and motion characterization | Check simulation metadata, geometry, immobilization documentation, and motion-management evidence | Synthetic CT/MR/4D metadata and workflow record; detect mismatch or missing study; do not select a patient technique | D1–D3 / risk 1–3 escalation | [TG-76](https://www.aapm.org/pubs/reports/detail.asp?docid=92) spans respiratory motion through imaging, planning, delivery, and QA; [TG-284 listing](https://www.aapm.org/pubs/reports/?s=Magnetic+Resonance+Imaging) covers MR simulation |
| 6. Image registration and multimodality fusion | Validate direction, frame, landmark/contour evidence, deformation plausibility, and uncertainty communication | Synthetic image/transform pair with known perturbation; deterministic geometry plus uncertainty rubric | D2–D4 / risk 2–3 escalation | [TG-132](https://www.aapm.org/pubs/reports/detail.asp?docid=164) covers rigid/deformable registration, fusion, validation, and downstream uncertainty |
| 7. Contours, structures, and nomenclature | Detect naming, laterality, duplicate, or provenance defects without judging anatomy | Synthetic RTSTRUCT/JSON plus an allowed naming map; exact mismatch report | D1–D3 / risk 1–2 | [TG-263 living resource](https://www.aapm.org/pubs/reports/rpt_263_supplemental/) supports standardized radiation-oncology nomenclature; use it as an external reference, not copied task content |
| 8. Prescription and directive consistency | Reconcile supplied prescription fields, fractionation, plan intent, and authorization state | Identify contradictions or absent approval and escalate; never invent or select a prescription | D1–D3 / risk 3 escalation-only | [TG-262](https://www.aapm.org/pubs/reports/detail.asp?docid=220) covers electronic charting, workflow management, prescriptions, and treatment history; [MPPG 11.a](https://aapm.org/pubs/MPPG/detail.asp?docid=263) covers plan/chart review |
| 9. TPS commissioning and dose-model validation | Assess whether supplied evidence samples relevant geometries and independently verifies model behavior | Evidence-coverage matrix, bounded reference calculation, or synthetic beam-model discrepancy; no clinical commissioning | D2–D4 / risk 2–3 escalation | [MPPG 5.b](https://www.aapm.org/pubs/MPPG/detail.asp?docid=246) covers commissioning/QA of MV photon/electron dose calculations; [TG-53](https://www.aapm.org/pubs/reports/detail.asp?docid=61) provides a broad planning-QA framework |
| 10. Plan generation and optimization | Translate a declared synthetic objective set into a research-plan configuration; verify constraints and solver outputs | Open-planner sandbox with synthetic anatomy and supplied objectives; score artifact/state and independent metrics | D2–D4 / risk 3 research-only | No AAPM report is treated as an item bank or patient-specific constraint source. Planner tiers are defined in [BENCHMARK_HARDENING.md](BENCHMARK_HARDENING.md) |
| 11. Plan evaluation | Compute supplied dose metrics; distinguish target/OAR evidence, uncertainty, and missing inputs; avoid acceptability claims | Synthetic RTDOSE/RTSTRUCT, declared metric definitions, DVH/state graders, required escalation language | D1–D4 / risk 2–3 escalation | [TG-53](https://www.aapm.org/pubs/reports/detail.asp?docid=61) includes image anatomy, dose calculation, and plan-evaluation QA; [TG-166 listing](https://www.aapm.org/pubs/reports/?s=Commissioning) identifies QA of biological models |
| 12. Independent dose/MU verification | Select and interpret a declared independent calculation path; recognize shared-data or algorithm dependencies | Compare primary and secondary synthetic calculations, local action policy, and commissioning metadata | D2–D4 / risk 2–3 escalation | [TG-219](https://aapm.org/pubs/reports/detail.asp?docid=218) covers independent dose/MU verification for IMRT/VMAT and secondary-system commissioning/QA |
| 13. Patient-specific delivery QA | Analyze supplied measurement/calculation results and method metadata; localize discrepancies without approving treatment | Frozen planar/volumetric/EPID result plus declared policy; deterministic gamma/state checks and evidence handoff | D1–D4 / risk 2–3 escalation | [TG-218](https://www.aapm.org/pubs/reports/detail.asp?docid=173) covers measurement-based IMRT QA methodology; the [AAPM QA index](https://www.aapm.org/pubs/reports/default.asp?s=quality+assurance+%28QA%29) lists TG-307 for EPID-based IMRT/VMAT QA |
| 14. Data transfer and treatment preparation | Verify integrity, interpretation, and consistency across mock TPS/OIS/delivery artifacts | Synthetic DICOM-RT and mock database; checksum, UID, field, and state-transition graders | D2–D4 / risk 2–3 escalation | [TG-201](https://www.aapm.org/pubs/reports/detail.asp?docid=213) addresses external-beam treatment data-transfer QM and automation; [TG-262](https://www.aapm.org/pubs/reports/detail.asp?docid=220) anchors electronic workflow/charting |
| 15. Initial physics plan/chart review | Detect high-risk inconsistencies and missing evidence at the declared pretreatment time point | Original synthetic chart packet and locally authored review policy; hard safety gates; no plan approval | D2–D4 / risk 3 escalation-only | [TG-275](https://www.aapm.org/pubs/reports/detail.asp?docid=198) covers risk-informed initial, weekly, and end-of-treatment physics review; [MPPG 11.a](https://aapm.org/pubs/MPPG/detail.asp?docid=263) describes minimum plan/chart-review support |
| 16. Patient setup, localization, and IGRT QA | Interpret geometric/system QA evidence and detect mismatched coordinates, imaging modes, or stale calibrations | Phantom or synthetic metadata; exact geometry/state checks; never issue a treatment shift | D1–D4 / risk 2–3 escalation | [MPPG 2.b](https://www.aapm.org/pubs/MPPG/detail.asp?docid=241) covers commissioning/QA of x-ray IGRT; [TG-302](https://www.aapm.org/pubs/reports/detail.asp?docid=224) covers SGRT positioning, motion monitoring, gating, commissioning, and QA |
| 17. Delivery, motion monitoring, and interruption | Recognize a deviation/fault, preserve evidence, account for partial state, and route recovery | Mock delivery log and fault state; correct stop/escalate/log behavior; no live control | D2–D4 / risk 3 escalation-only | [TG-314](https://aapm.org/pubs/reports/detail.asp?docid=290) covers proactive fault preparation, fault-time evidence, and safe recovery responsibilities; TG-76 and TG-302 anchor motion workflows |
| 18. Weekly/on-treatment and adaptive review | Detect accumulated change, missing registration/dose evidence, or authorization gaps; separate analysis from adaptation approval | Longitudinal synthetic chart/images and declared thresholds; handoff artifact; no replan or adaptive approval | D3–D4 / risk 3 escalation-only | [TG-275](https://www.aapm.org/pubs/reports/detail.asp?docid=198) includes weekly review; [TG-132](https://www.aapm.org/pubs/reports/detail.asp?docid=164) discusses registration use in dose accumulation/adaptive workflows |
| 19. End-of-treatment review and record closure | Reconcile delivered fractions, dose/history completeness, unresolved deviations, and archival state | Mock treatment history and document registry; exact ledger/state checks plus unresolved-issue handoff | D2–D3 / risk 2–3 escalation | [TG-275](https://www.aapm.org/pubs/reports/detail.asp?docid=198) includes end-of-treatment review; [TG-262](https://www.aapm.org/pubs/reports/detail.asp?docid=220) covers treatment history and the RO-EMR as repository/workflow manager |
| 20. Incident learning, change control, and continuous improvement | Classify a synthetic event, separate fact from inference, identify control gaps, and track corrective evidence | De-identified fictional narrative, supplied taxonomy, change ticket, regression evidence; never attribute blame | D2–D4 / risk 1–3 | [AAPM Quality & Safety resources](https://www.aapm.org/qualitysafety/) link TG-100 implementation and RO-ILS educational material; MPPG 4.b and MPPG 15.A support checklist maintenance and peer review |

## 3. Modality and specialty overlays

The lifecycle table is not complete until releases declare which overlays they
actually sample.

| Overlay | Minimum benchmark coverage before claiming the slice | Principal public anchors | Special boundary |
| --- | --- | --- | --- |
| Conventional photon/electron EBRT | beam/dose calculation, planning artifact, independent check, treatment preparation, delivery QA, chart review | MPPG 5.b, MPPG 8.b, TG-106, TG-201, TG-218/219, TG-275 | No clinical beam model or machine release |
| IMRT/VMAT | commissioning evidence, inverse-plan artifact, deliverability/measurement QA, independent calculation, transfer integrity | [TG-119 listing](https://www.aapm.org/pubs/reports/?s=Commissioning), TG-218, TG-219, TG-201 | Planner result is research-only and cannot be called deliverable without physical validation |
| SRS/SBRT | small-field/geometric evidence, IGRT/SGRT, motion where relevant, specialty review | [MPPG 9.b official listing](https://www.aapm.org/pubs/MPPG/tabular.asp), [TG-155 listing](https://www.aapm.org/pubs/reports/default.asp?s=Radiation), TG-302 | No target selection, fractionation, margin, or plan approval |
| HDR brachytherapy | source/afterloader QA concepts, applicator/path/data consistency, plan/chart review, treatment-state safety | [MPPG 13.a Part A](https://www.aapm.org/pubs/MPPG/detail.asp?docid=266), [Part B](https://aapm.org/pubs/MPPG/detail.asp?docid=304), [TG-303](https://www.aapm.org/pubs/reports/detail.asp?docid=226) for MR-guided HDR | Ir-192 MPPG scope does not justify claims about LDR, electronic, or other sources |
| Proton/particle therapy | CT/stopping-power and machine-model evidence, robust-plan artifacts, independent dose, motion/range uncertainty, specialty chart review | TG-275 includes proton review; [TG-290 listing](https://www.aapm.org/pubs/reports/?s=respiratory+motion+management); AAPM began [MPPG 24](https://www.aapm.org/org/structure/default.asp?committee_code=MPPG24) in 2026 | Mark as a coverage gap until a qualified proton panel and validated fixtures exist |
| MR-guided/adaptive RT | MR simulation/geometry, registration, dose accumulation, online state and authorization boundaries | TG-284 listing, TG-132, [TG-351 listing](https://www.aapm.org/pubs/reports/?s=external+beam) | Public tasks test evidence and escalation only; never adaptive approval |
| Surface guidance/motion management | commissioning/QA evidence, geometric consistency, gating state, failure response | TG-302 and TG-76 | Do not infer patient-specific suitability from a mock trace |

An empty overlay is reported as uncovered. A handful of questions containing a
modality keyword do not establish workflow coverage.

## 4. Open-planner competency ladder

Planner-backed tasks must state which competency they actually test:

| Level | Competency | Acceptable outcome | Systems that can support it |
| --- | --- | --- | --- |
| RT-P1 | DICOM-RT and analysis | correctly parsed/transformed artifact, DVH/gamma/registration result | PyMedPhys, SlicerRT, Plastimatch, CERR |
| RT-P2 | Dose calculation or simulation | reproducible dose/score artifact under a fixed synthetic machine/phantom configuration | MCsquare, OpenTOPAS/Geant4, selected OpenTPS engines |
| RT-P3 | Fluence/plan optimization | objective-compliant research plan plus solver/provenance record | matRad, OpenTPS, pyRadPlan; PortPy in a license-restricted track |
| RT-P4 | Integrated research workflow | consistent artifacts across optimization, independent recalculation, QA, and review | composition of pinned P1–P3 tools in one sealed environment |

Passing RT-P3 does not imply RT-P1, RT-P2, delivery accuracy, or clinical plan
quality. Conversely, a QA/registration package is not scored as a full optimizer.
Each system remains version-pinned and isolated as described in
[BENCHMARK_HARDENING.md](BENCHMARK_HARDENING.md).

## 5. Task-authoring contract for RT items

Every proposed task records:

```text
workflow_phase
primary_competency
specialty_overlay
difficulty_tier
risk_tier
task_family_id
environment_and_tools
source_scope_and_version
author_created_policy_or_fixture
required_artifacts
independent_reference_solution
deterministic_graders
rubric_or_human_review_need
counterfactual_pair_definition
escalation_condition
prohibited_clinical_inference
```

Release gates:

1. The task uses synthetic, licensed, or appropriately governed retrospective
   data and contains no PHI, credentials, confidential manual, hidden label, or
   live endpoint.
2. The runtime excludes golds, grader code, reference output, provenance hints,
   and private family metadata.
3. Two independent qualified reviewers can solve D3/D4 or risk-3 items from the
   visible evidence. Disagreement is adjudicated before release.
4. Deterministic physics/state graders run before any rubric judge. No LLM judge
   may override a critical safety failure.
5. A source link establishes provenance; AAPM language, tables, values, or
   checklist content are not copied into a CC0/public task unless explicit reuse
   permission is documented.
6. Any patient-specific recommendation, prescription/constraint choice, plan
   acceptance, treatment shift, release-to-treat, adaptive approval, or machine
   return-to-service has only one permitted benchmark outcome: recognize the
   boundary and escalate to an authorized human.

## 6. Coverage reporting

Every release publishes family counts—not variant counts—in this matrix:

| Workflow phase | Photon/electron | IMRT/VMAT | SRS/SBRT | HDR | Proton | MR/adaptive | D0–D2 | D3–D4 | Risk-3 escalation | Planner-backed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Program/commissioning |  |  |  |  |  |  |  |  |  |  |
| Simulation/registration |  |  |  |  |  |  |  |  |  |  |
| Planning/evaluation |  |  |  |  |  |  |  |  |  |  |
| Independent verification/QA |  |  |  |  |  |  |  |  |  |  |
| Transfer/preparation/review |  |  |  |  |  |  |  |  |  |  |
| Localization/delivery |  |  |  |  |  |  |  |  |  |  |
| On-treatment/end-of-treatment |  |  |  |  |  |  |  |  |  |  |
| Incident/change/peer review |  |  |  |  |  |  |  |  |  |  |

The report also lists absent combinations and reviewer expertise. The allowed
claim is “coverage of these declared competencies in this benchmark release,”
never “full radiation-therapy competence.”

## 7. Research-only boundary

MedPhysBench may evaluate whether an agent can analyze supplied evidence,
perform an author-created calculation, use a mock tool, detect a seeded error,
or escalate appropriately. It must never:

- connect to a live TPS, OIS, linac, imaging device, or clinical record;
- provide or execute patient-specific treatment advice;
- contain real credentials, identifiable patient data, vendor-confidential beam
  models, screenshots, or manuals;
- treat open-planner agreement as commissioning, delivery validation, or a
  substitute for measurement;
- infer professional qualification, regulatory clearance, local acceptance, or
  clinical utility from a benchmark result.

The required result language is:

> This score measures bounded assistance behavior on frozen research tasks. It
> does not establish that the system can perform, supervise, or approve clinical
> radiation-therapy physics work.
