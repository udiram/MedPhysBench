# Access-probe receipts

This directory accepts immutable `medphysbench.access-probe-receipt.v1` JSON
artifacts produced by provider-specific route probes. A receipt is operational
evidence only: it never contains a model answer, grade, patient data, credential,
raw provider body, or benchmark score.

Successful receipts must bind an exact route specification hash and expire within
that route's declared access TTL. They must postdate the frozen route set, prove
the route's declared response contract, and bind the repository-relative path and
SHA-256 of the reviewed probe implementation. Failure receipts may document unavailable
models, missing authorization, quota exhaustion, rate limiting, unsupported
contracts, or network failure. No receipt—successful or failed—changes the public
evaluated/ranked counts by itself.

Do not hand-author a successful receipt. Use a reviewed probe implementation,
validate its self-hash, and preserve it with the generated campaign and eventual
common-harness submission.
