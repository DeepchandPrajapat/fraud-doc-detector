# Fraud Document Detection — V1

Checks onboarding documents (Aadhaar, PAN, degree certificate, marksheets, optional selfie)
for fraud and returns PASS / REVIEW / REJECT with reasons. Rejections are suggestions; HR confirms.

## Layout

```
config/settings.py          all thresholds/paths (override via FDD_* env vars)
fdd/schemas.py              data contracts: DocumentObject, Signal, ModuleResult, reports
fdd/intake/                 Stage 2: file_check, quality gate, document classifier
fdd/extraction/             Stage 3: OCR, field extractors, QR (Aadhaar Secure QR), metadata, photo crop
fdd/modules/                Stages 4-5: fraud modules F1..F12 (base.py = interface + registry)
fdd/fusion/fuse.py          Stage 6: signals -> score -> verdict
fdd/pipeline.py             orchestrator: ingest() one file, analyse() a candidate
scripts/inspect_document.py debug: show everything extracted from one file
data/reference_lists/       UGC/AICTE/board lists, UIDAI public cert (to be added)
data/samples/               test documents (keep masked; never commit real IDs)
```

## Run

```bash
pip install -r requirements.txt
pytest                                                     # foundation tests
python scripts/inspect_document.py some_aadhaar.jpg        # inspect extraction
python scripts/inspect_document.py pan.pdf --ocr tesseract
```

## Adding a fraud module

```python
from fdd.modules.base import FraudModule, register
from fdd.schemas import DocType, ModuleResult, ModuleStatus, Signal, Severity

@register
class IdValidity(FraudModule):
    fraud_id, name = "F1", "ID number validity"
    applies_to = {DocType.AADHAAR, DocType.PAN}
    scope = "document"            # or "candidate" for cross-document checks

    def run(self, docs, profile) -> ModuleResult:
        ...
        return ModuleResult(fraud_id="F1", status=ModuleStatus.CHECKED, signals=[...])
```
Import the module in `fdd/modules/__init__.py` so it registers.

## V1 modules

| ID | Module | Status |
|----|--------|--------|
| F1 | ID validity + Aadhaar Secure QR | todo |
| F2 | Identity consistency | todo |
| F3 | Resume vs education docs | todo |
| F4 | Education timeline | todo |
| F5 | Fake university / board | todo |
| F7' | Marksheet arithmetic | todo |
| F8 | PDF / metadata editing | todo |
| F9 | Pixel tampering | todo |
| F11 | Face match (selfie optional, Aadhaar↔PAN always) | todo |
| F12 | Fully fabricated documents | todo |
