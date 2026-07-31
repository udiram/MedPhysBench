# LIDC-IDRI CT fixture attribution

The PNG in this directory is a transformed axial DICOM slice from the public
LIDC-IDRI collection hosted by The Cancer Imaging Archive (TCIA).

- Source collection: [LIDC-IDRI](https://www.cancerimagingarchive.net/collection/lidc-idri/)
- Series Instance UID: `1.3.6.1.4.1.14519.5.2.1.6279.6001.314917368146772872954571551463`
- License: [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)
- Changes: selected the median axial slice, applied a -1000 to 400 HU display window,
  converted it to 8-bit PNG, and added a 16 by 16 cyan grid.

The source archive, transform, and output hashes are recorded in `manifest.json`.
The derived lung-air mask is a deterministic research target, not a clinical contour.
The fixture must not be used to identify or contact any participant.
