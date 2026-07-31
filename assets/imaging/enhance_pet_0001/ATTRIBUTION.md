# ENHANCE.PET fixture attribution

The PNG in this directory is a transformed whole-body FDG PET study from the
ENHANCE.PET 1.6k public AWS dataset. Subject `0001` originates from the AutoPET
Challenge cohort and is therefore used under CC BY-NC 4.0.

- Dataset: [ENHANCE.PET 1.6k](https://registry.opendata.aws/enhance-pet-1-6k/)
- Source cohort: AutoPET Challenge
- License: [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)
- Changes: coronal maximum-intensity projection, log transform, 99.5th-percentile
  clipping, resize to 512 by 768 pixels, and a 16 by 24 cyan grid.

Exact source and output hashes are recorded in `manifest.json`. This non-commercial
fixture is for research evaluation only and must not be used for patient diagnosis.
