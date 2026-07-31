# Data statement

## Composition

The public development release contains authored YAML task packs and small inline context
artifacts. Inputs are synthetic or deliberately redistributable source packets. No patient data,
protected health information, clinical credentials, or proprietary treatment-system exports are
required or permitted.

## Provenance and licensing

Every task declares `source_class`, `authoring_status`, license, creation time, and PHI review.
Public task fixtures are released under CC0-1.0; harness code is MIT licensed. A task must be
excluded if its provenance or redistribution right cannot be established.

## Labels

Grading specifications and reference values are authored from explicit formulas, supplied policy
packets, or declared acceptance rules. Public labels are intentionally inspectable. They are not a
holdout and should be assumed accessible to model developers.

## Sensitive and restricted data

Future gated or private suites must use separate storage, access control, audit logging, retention,
and publication policies. Restricted labels must never be mounted into a candidate sandbox or
committed to public CI. De-identification alone does not authorize redistribution.

## Representativeness

The 16-task release is not statistically representative of medical-physics practice. Task counts
reflect an initial engineering suite, not workforce prevalence, clinical risk, or importance.
Aggregate scores must therefore be read together with the task catalog and domain results.
