# Reference Landscape

This project should use primary sources and official benchmark documentation when
making claims about benchmark methods, hardware, or clinical AI implementation.
The list below is a starting source ledger, not an endorsement of every method or
product.

## Medical-physics and health-AI context

- [IAEA — Clinical Implementation of Artificial Intelligence Systems in Medical Imaging and Radiotherapy (2025)](https://www-pub.iaea.org/MTCD/publications/PDF/p15925-PUB2135_web.pdf) — implementation/validation, roles, local evaluation, lifecycle monitoring.
- [IAEA — Artificial Intelligence in Medical Physics (2023)](https://www-pub.iaea.org/MTCD/Publications/PDF/TCS83web.pdf) — scope and medical-physics AI context.
- [AAPM TG-275 — Methods and processes of artificial intelligence in medical physics](https://www.aapm.org/pubs/reports/detail.asp?docid=198) — best-practice context for clinical AI-related physics work.
- [AAPM TG-100 — Risk analysis methods for radiation therapy quality management](https://www.aapm.org/pubs/reports/detail.asp?docid=156) — risk-analysis framing.
- [AAPM TG-142 — Quality assurance of medical accelerators](https://www.aapm.org/pubs/reports/detail.asp?docid=125) — example source for carefully licensed/internal QA task construction.
- [FDA — Good Machine Learning Practice guiding principles](https://www.fda.gov/medical-devices/software-medical-device-samd/good-machine-learning-practice-medical-device-development-guiding-principles) — lifecycle and evaluation concepts.
- [FDA — Transparency for machine-learning-enabled medical devices](https://www.fda.gov/medical-devices/software-medical-device-samd/transparency-machine-learning-enabled-medical-devices-guiding-principles) — transparency framing.
- [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework) and [NIST Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) — risk governance framework.
- [HHS HIPAA de-identification guidance](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html) — data handling baseline.
- [WHO ethics and governance of AI for health](https://www.who.int/publications/i/item/9789240029200) and [WHO guidance on large multi-modal models](https://www.who.int/publications/i/item/9789240084759) — health-AI governance context.

## Existing and adjacent benchmarks

No public benchmark was found that already supplies the full proposed combination
of medical-physics-wide coverage, sealed agent-tool environments, outcome/state
grading, and safety/escalation measurement. There are important adjacent efforts:

- [Radiation oncology physics language-model evaluation](https://pmc.ncbi.nlm.nih.gov/articles/PMC12141255/) — specialized physics knowledge assessment.
- [MedAgentBench](https://stanfordmlgroup.github.io/projects/medagentbench/) — medical, tool-using agent benchmark; closest architectural analogue.
- [HealthAgentBench](https://microsoft.github.io/HealthAgentBench/) — health-agent evaluation environment.
- [HealthBench](https://openai.com/index/healthbench/) — physician-developed health conversations and quality evaluation.
- [MedHELM](https://medhelm.org/medhelm) — medical benchmark evaluation framework.
- [AgentClinic](https://agentclinic.github.io/) — sequential, multimodal, tool-using clinical evaluation.
- [OpenKBP](https://arxiv.org/abs/2011.14076) and [AAPM MATCH](https://www.aapm.org/GrandChallenge/MATCH/) — examples of radiation-therapy challenge/data ecosystems, not end-to-end agent benchmarks.
- [SynthRAD challenge](https://synthrad2023.grand-challenge.org/) — imaging/radiotherapy task challenge pattern.

## Frontier-style eval patterns

- [HELM](https://crfm.stanford.edu/helm/) / [paper](https://arxiv.org/abs/2211.09110) — scenario-by-metric evaluation rather than a single score.
- [GAIA](https://huggingface.co/datasets/gaia-benchmark/GAIA) / [paper](https://arxiv.org/abs/2311.12983) — realistic assistant tasks, difficulty levels, public/private access pattern.
- [AgentBench](https://github.com/THUDM/AgentBench) — multiple environments and agent tracks.
- [OSWorld](https://osworld-v1.xlang.ai/) / [paper](https://arxiv.org/abs/2404.07972) — environment-state outcomes, not answer preference alone.
- [SWE-bench Verified](https://www.swebench.com/verified.html) and [OpenAI’s description](https://openai.com/index/introducing-swe-bench-verified/) — reproducible environments, hidden tests, and human task-quality review.
- [OpenAI evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices) — task-specific, continuous, calibrated evaluation guidance.
- [Anthropic — Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) — task/trial/grader language and agent reliability metrics.
- [Google Cloud agent evaluation overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/optimize/evaluation/evaluate-agents) — outcome and trajectory evaluation concepts.

## Harness and tool-virtualization stack

- [Temporal documentation](https://docs.temporal.io/) — durable workflows.
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/) — portable tracing.
- [Langfuse documentation](https://langfuse.com/docs) — AI trace/review platform option.
- [Pydantic validation documentation](https://docs.pydantic.dev/latest/) — typed output boundary.
- [Orthanc](https://www.orthanc-server.com/static.php?page=documentation), [Orthanc DICOMweb plugin](https://orthanc.uclouvain.be/book/plugins/dicomweb.html), [pydicom](https://pydicom.github.io/pydicom/), and [dicomweb-client](https://dicomweb-client.readthedocs.io/) — frozen DICOM fixture environments.
- [gVisor](https://gvisor.dev/docs/user_guide/production/) and [Firecracker](https://firecracker-microvm.github.io/) — sandbox isolation options.
- [vLLM OpenAI-compatible serving](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/) — local model-serving option.

## Open radiation-therapy research tools

- [matRad documentation](https://matrad.readthedocs.io/en/dev/) and [official project](https://e0404.github.io/matRad/) — multimodality research planning and optimization.
- [OpenTPS](https://www.opentps.org/) and [official license page](https://opentps.org/about/licence.html) — Python research TPS with proton-focused planning, dose, imaging, registration, and QA capabilities.
- [OpenKBP-Opt](https://github.com/ababier/open-kbp-opt) — reproducible knowledge-based planning optimization code and data.
- [CERR](https://github.com/cerr/CERR) — MATLAB/Octave radiological-research environment.
- [SlicerRT](https://github.com/SlicerRt/SlicerRT) — DICOM-RT, visualization, analysis, contour, dose, and research-planning extension for 3D Slicer.
- [Plastimatch](https://plastimatch.org/) — registration, DICOM-RT, image conversion, gamma, and segmentation metrics.
- [OpenTOPAS](https://opentopas.github.io/) and [GATE 10](https://github.com/OpenGATE/opengate) — open Monte Carlo platforms applicable to therapy, imaging, and dosimetry research.

The executable-adapter scope and resource limits are specified in
[PLANNING_SANDBOX.md](PLANNING_SANDBOX.md).

## Hardware and data operations

- [NVIDIA RTX PRO 6000 Blackwell Workstation Edition datasheet](https://www.nvidia.com/content/dam/en-zz/Solutions/data-center/rtx-pro-6000-blackwell-workstation-edition/workstation-blackwell-rtx-pro-6000-workstation-edition-nvidia-us-3519208-web.pdf)
- [NVIDIA DGX Spark hardware documentation](https://docs.nvidia.com/dgx/dgx-spark/hardware.html)
- [AWS S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
- [AWS P5 instance family](https://aws.amazon.com/ec2/instance-types/p5/) and [Google Cloud GPU documentation](https://cloud.google.com/compute/docs/gpus) — examples of burst-compute classes, subject to current availability.

## Citation and source-use policy

Use this list as a discovery map. For actual tasks, record exact source version,
terms/license, accessed date, allowed transformation, and task-specific rationale
in the provenance ledger. Do not distribute copyrighted standards, vendor manuals,
or restricted institutional artifacts merely because they are useful for internal
task design.
