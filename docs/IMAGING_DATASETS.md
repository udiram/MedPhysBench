# Imaging dataset registry

This registry separates datasets we can cite, datasets from which a reduced
fixture may be redistributed, and datasets that require gated or non-commercial
handling. “Public” never means “permission-free.” Exact collection terms govern.

| Dataset | Modality and benchmark role | Size | Terms and handling | MedPhysBench status |
|---|---|---:|---|---|
| [Medical Segmentation Decathlon](https://medicaldecathlon.com/) | CT/MRI organ and lesion segmentation across ten tasks | 2,633 images | CC BY-SA 4.0; preserve attribution and share-alike terms for derived fixtures | One real MRI slice and hidden paired label are integrated in the public v0.4 imaging pilot. |
| [LIDC-IDRI](https://www.cancerimagingarchive.net/collection/lidc-idri/) | Thoracic CT, lung-nodule localization and radiologist annotations | 1,018 subjects / about 125 GB | TCIA CC BY 3.0 plus TCIA data-use policy | One hash-pinned axial CT and deterministic coarse lung-air target are integrated in v0.4. |
| [C4KC-KiTS](https://wiki.cancerimagingarchive.net/pages/viewpage.action?pageId=61081171) | Contrast CT kidney/tumor segmentation | 210 public training cases | TCIA CC BY 3.0 with required citation | Approved next CT segmentation candidate. |
| [BraTS 2021](https://wiki.cancerimagingarchive.net/display/DOI/RSNA-ASNR-MICCAI-BraTS-2021) | Multi-sequence MRI glioma segmentation | 2,040 cohort; 1,480 currently available through TCIA | Brain-extracted challenge package is CC BY 4.0; some source DICOM requires a restricted agreement and has face re-identification concerns | Only the explicitly licensed NIfTI route is eligible for public derived fixtures. Raw restricted DICOM is excluded. |
| [BraTS-PEDs](https://www.cancerimagingarchive.net/collection/brats-peds/) | Pediatric glioma MRI segmentation | 457 patients | CC BY 4.0 with attribution | Candidate for a separately reviewed pediatric MRI family. |
| [autoPET](https://autopet.grand-challenge.org/Dataset/) | Whole-body FDG PET/CT lesion segmentation | 1,014 public studies | Training data is non-commercial under the challenge terms | Isolated non-commercial evaluation family; not mixed into the general public package. |
| [ENHANCE.PET 1.6k](https://registry.opendata.aws/enhance-pet-1-6k/) | PET/CT reconstruction and structure labels | 1,597 studies / about 250 GB | Mixed licenses by subset, including CC BY and CC BY-NC | One AutoPET-subset MIP is integrated under CC BY-NC 4.0 in the separate non-commercial pilot. |

## Fixture contract

Every committed reduced fixture must include its source URL, original member or
series identifier, upstream license, original and derived SHA-256 hashes,
transform log, modality/orientation/spacing metadata, and a research-only use
statement. The model-visible artifact may contain the image, but never the paired
gold mask or a path that resolves to it.

Current fixtures and deterministic builders live under [`assets/imaging/`](../assets/imaging/)
and [`scripts/`](../scripts/). Builders take a locally downloaded, hash-pinned
upstream artifact and never perform an implicit network download.
