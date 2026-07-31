# Knowledge-source and exam-content policy

MedPhysBench tests medical-physics knowledge without redistributing confidential
exam content or copyrighted board-preparation material. Public task wording is
original benchmark authoring; a citation is evidence for the underlying concept,
not permission to copy a source.

## Source classes

| Class | Public-task use | Examples |
|---|---|---|
| Green | May ground a public deterministic answer when the cited material is public-domain or its terms permit the use. | NIST data and calculations; eCFR/NRC regulations; author-created synthetic fixtures. |
| Amber | May guide taxonomy, realism, and independent validation. Do not copy prose, tables, figures, or question wording into CC0 task files. | IAEA handbooks, AAPM reports, QIBA profiles, the DICOM Standard, NCRP/ICRP publications. |
| Red | Never use as an item bank or close-paraphrase source. | ABR exam items or recalled content; RAPHEX questions/answers; vendor or institutional confidential material. |

## ABR and RAPHEX boundary

The public [ABR medical-physics content guides](https://www.theabr.org/get-certified/medical-physics/)
are used only to check topic coverage. ABR exam content is confidential and
copyrighted under the [ABR Exam Integrity Policy](https://www.theabr.org/wp-content/uploads/2025/07/Exam-Integrity-Policy-2024.pdf).
RAPHEX is a commercial, copyrighted practice examination; MedPhysBench does not
copy, paraphrase, scrape, or reconstruct its items. The public suite therefore
tests the same broad competencies through newly authored calculations, audits,
and evidence packets, not exam clones.

## Approved public ground-truth sources

- [NIST photon attenuation and XCOM resources](https://www.nist.gov/pml/x-ray-mass-attenuation-coefficients)
- [NIST copyright and reuse statement](https://www.nist.gov/copyrights-disclaimers)
- [10 CFR 20 occupational dose limits](https://www.ecfr.gov/current/title-10/chapter-I/part-20/subpart-C/section-20.1201)
- Author-created policies and synthetic DICOM metadata validated against the
  [current DICOM Standard](https://www.dicomstandard.org/current)

IAEA, AAPM, and QIBA sources remain important scientific references. Their
copyright and permission terms mean they are used for concept validation and
citations, not as redistributable benchmark text. See the
[IAEA rights statement](https://www.iaea.org/publications/rights-and-permissions)
and [AAPM permissions page](https://www.aapm.org/pubs/CopyrightPermissions.asp).

## Required provenance fields

Every reviewed task should eventually record:

- source URL and owner;
- source class and license status;
- ground-truth basis and independent calculation or reference solution;
- whether copied text is present (normally `false`);
- whether public redistribution is permitted;
- reviewer identity, review date, and permission status when applicable.

Unclear permission is a release blocker, not a reason to omit attribution.
