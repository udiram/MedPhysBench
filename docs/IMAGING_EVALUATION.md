# Real-image evaluation protocol

The v0.4 imaging pilot is an executable proving ground for image transport,
integrity checks, localization, and segmentation scoring. It is intentionally
reported separately from the core knowledge suite.

## Runtime boundary

Agent-visible images use an `asset://` reference with a mandatory SHA-256
fragment. The harness resolves the path below a configured artifact root, rejects
path traversal, verifies the digest, and sends the bytes through the provider's
native vision input. Base64 pixels are not pasted into the text prompt. Gold
geometry remains in the authoring/grader view and is absent from the serialized
runtime task.

## Current public tasks

1. `real-mri-hippocampus-localization-001` returns one XYXY box and is scored by
   intersection over union against the paired MSD label.
2. `real-mri-hippocampus-segmentation-001` returns unique cells on a visible
   16 by 16 grid and is scored by Dice. This coarse representation is a transport
   and spatial-reasoning pilot, not a substitute for 3D clinical segmentation.
3. `real-ct-lung-segmentation-001` uses a LIDC-IDRI chest CT slice and grades a
   coarse lung-air mask against a deterministic HU/connected-component reference.
4. `real-pet-bladder-localization-001` localizes physiologic bladder activity on
   an ENHANCE.PET whole-body FDG PET MIP with bounding-box IoU.
5. `real-pet-cohort-classification-001` predicts the released AutoPET study-level
   label and requires clinical escalation. It is reported as source-label
   classification, never diagnostic performance.

The pass gates are fixed before model execution. Invalid schemas, duplicate grid
cells, non-finite coordinates, degenerate boxes, digest mismatches, and critical
safety-contract failures are explicit failures.

## Diagnosis and retrospective interpretation

MedPhysBench uses the term `retrospective_interpretation`, not “clinical
diagnosis,” for tasks based on released research labels. The public v0.4 pilot
contains one explicitly labeled, negative AutoPET example solely to validate the
transport, classification, and escalation contracts. It is not a cohort and no
diagnostic accuracy estimate is calculated. A sound interpretation
family needs a licensed cohort, prespecified endpoint, patient-level split,
clinician/physicist review, uncertainty reporting, subgroup checks, and a blinded
holdout. It must not be inferred from one convenient public image or scored from
unverified web captions. Until those controls exist, no diagnostic-performance
claim is published.

## Planned expansion

- full-resolution NIfTI mask submission with Dice, IoU, HD95, ASSD, volume error,
  and empty-mask edge cases;
- CT nodule localization using LIDC-IDRI radiologist annotations;
- CT kidney/tumor segmentation using KiTS;
- larger licensed multi-sequence MRI and non-commercial PET families in isolated pools;
- a blinded retrospective-interpretation review lane with model identity hidden
  from adjudicators.
