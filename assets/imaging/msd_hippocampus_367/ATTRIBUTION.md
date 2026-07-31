# MSD hippocampus fixture attribution

The two PNG images in this directory are transformed from
`Task04_Hippocampus/imagesTr/hippocampus_367.nii.gz` in the Medical
Segmentation Decathlon (MSD). The hidden reference geometry was derived from
the paired `labelsTr/hippocampus_367.nii.gz` label.

- Source: [Medical Segmentation Decathlon](https://medicaldecathlon.com/)
- Upstream package: [Task04_Hippocampus.tar](https://msd-for-monai.s3.amazonaws.com/Task04_Hippocampus.tar)
- Dataset description: Vanderbilt University Medical Center, “Left and right hippocampus segmentation”
- Upstream and derived-fixture license: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- Changes: axial slice 16 was intensity-windowed at its 1st and 99th percentiles, transposed, vertically flipped, and resized using nearest-neighbor interpolation. The grid variant adds a 16 by 16 cyan overlay.

Exact source, transform, and output hashes are recorded in `manifest.json`.
The fixture is for research benchmark evaluation only and is not intended for
diagnosis or clinical use.
