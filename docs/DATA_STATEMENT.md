# Data statement

## Composition

The public releases contain authored YAML task packs, small synthetic context artifacts, and three
reduced image-fixture families derived from de-identified public research datasets. No protected
health information, clinical credentials, or proprietary treatment-system exports are required or
permitted. The real MRI, CT, and PET pixels are retrospective research data and remain subject to
their upstream licenses and data-use terms.

## Provenance and licensing

Every task declares `source_class`, `authoring_status`, license, creation time, and PHI review.
Original public task text is released under CC0-1.0; harness code is MIT licensed. Derived images
retain their declared upstream terms: CC BY-SA 4.0 for MSD, CC BY 3.0 for LIDC-IDRI, and CC BY-NC
4.0 for the AutoPET-derived ENHANCE.PET example. A task is excluded if provenance or redistribution
rights cannot be established.

## Labels

Grading specifications and reference values are authored from explicit formulas, supplied policy
packets, or declared acceptance rules. Public labels are intentionally inspectable. They are not a
holdout and should be assumed accessible to model developers.

## Sensitive and restricted data

Future gated or private suites must use separate storage, access control, audit logging, retention,
and publication policies. Restricted labels must never be mounted into a candidate sandbox or
committed to public CI. De-identification alone does not authorize redistribution.

## Representativeness

The 82-task hardening candidate, frozen 64-task scored core snapshot, and five-task real-image pilot are not statistically representative of
medical-physics practice. Task counts reflect an engineering suite, not workforce prevalence,
clinical risk, or importance. One released negative PET label cannot support a diagnostic metric.
Aggregate scores must therefore be read together with the task catalog and domain results.
