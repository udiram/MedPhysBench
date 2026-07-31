# Local platform services

`compose.platform.yaml` is a development convenience for PostgreSQL and MinIO.
It intentionally binds to loopback, contains placeholder development credentials,
and does not run a model, sandbox worker, DICOM server, or any clinical-system
integration.

Before any shared or restricted-data deployment, replace it with managed identity,
secret management, encrypted persistent storage, backups, network segmentation,
and an approved infrastructure review. See
[../../docs/HARDWARE_AND_DEPLOYMENT.md](../../docs/HARDWARE_AND_DEPLOYMENT.md).
