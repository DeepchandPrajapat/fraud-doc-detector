"""End-to-end orchestrator: Stage 1 (input) -> 7 (report)."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fdd.extraction.extract import extract
from fdd.extraction.ocr import run_ocr
from fdd.fusion.fuse import score_signals
from fdd.intake.classifier import classify
from fdd.intake.file_check import IntakeError, check_file, load_pages
from fdd.intake.quality import assess_quality
from fdd.modules.base import REGISTRY
from fdd.schemas import (
    REQUIRED_DOCS,
    CandidateProfile,
    CandidateReport,
    DocType,
    DocumentObject,
    DocumentReport,
    ModuleResult,
    ModuleStatus,
)

log = logging.getLogger("fdd")


def ingest(path: str | Path, declared_type: DocType | None = None) -> DocumentObject:
    """Stages 2-3 for one file. `declared_type` = slot the candidate uploaded into (optional)."""
    doc = DocumentObject(doc_id=uuid.uuid4().hex[:12], path=str(path), mime="")
    doc.mime = check_file(path)
    doc.pages = load_pages(path, doc.mime)

    # Quality gate: unreadable documents are sent back before any OCR or analysis.
    # (Selfie quality is judged separately by F11.)
    doc.quality = assess_quality(doc.pages[0])
    if declared_type != DocType.SELFIE and not doc.quality["ok"]:
        raise IntakeError("re-upload needed (" + ", ".join(doc.quality["issues"]) + ")")

    if declared_type == DocType.SELFIE:
        doc.doc_type, doc.classifier_confidence = DocType.SELFIE, 1.0
    else:
        doc.ocr_tokens = run_ocr(doc.pages)
        doc.full_text = "\n".join(t.text for t in doc.ocr_tokens)
        dtype, conf, scores = classify(doc.full_text)
        doc.classifier_confidence = conf
        doc.metadata["classifier_scores"] = scores
        # trust the upload slot unless OCR strongly disagrees
        if declared_type and dtype not in (declared_type, DocType.UNKNOWN) and conf > 0.5:
            doc.errors.append(f"declared {declared_type.value} but looks like {dtype.value}")
            doc.doc_type = dtype
        else:
            doc.doc_type = declared_type or dtype
    return extract(doc)


def _run_module(mod, docs, profile) -> ModuleResult:
    try:
        return mod.run(docs, profile)
    except Exception as e:  # noqa: BLE001 - one broken module must not kill the report
        log.exception("module %s failed", mod.fraud_id)
        return ModuleResult(fraud_id=mod.fraud_id, status=ModuleStatus.ERROR, error=str(e))


def analyse(files: list[tuple[str | Path, DocType | None]],
            profile: CandidateProfile) -> CandidateReport:
    docs: list[DocumentObject] = []
    intake_issues: list[str] = []

    for path, declared in files:
        try:
            doc = ingest(path, declared)
        except IntakeError as e:
            intake_issues.append(f"{Path(path).name}: {e}")
            continue
        if doc.doc_type == DocType.UNKNOWN:
            intake_issues.append(f"{Path(path).name}: document type not recognised")
        docs.append(doc)

    present = {d.doc_type for d in docs}
    missing = REQUIRED_DOCS - present
    if missing:
        intake_issues.append("missing documents: " + ", ".join(sorted(m.value for m in missing)))

    results: list[ModuleResult] = []
    for cls in REGISTRY:
        mod = cls()
        applicable = [d for d in docs if d.doc_type in mod.applies_to]
        if not applicable:
            results.append(mod.skipped("no applicable documents"))
            continue
        if mod.scope == "document":
            for d in applicable:
                results.append(_run_module(mod, [d], profile))
        else:
            results.append(_run_module(mod, applicable, profile))

    all_signals = [s for r in results for s in r.signals]
    doc_reports = []
    for d in docs:
        sigs = [s for s in all_signals if s.doc_id == d.doc_id]
        score, verdict = score_signals(sigs)
        doc_reports.append(DocumentReport(doc_id=d.doc_id, doc_type=d.doc_type,
                                          verdict=verdict, score=score, signals=sigs))
    cand_signals = [s for s in all_signals if s.doc_id is None]
    score, verdict = score_signals(all_signals)
    return CandidateReport(candidate_id=profile.candidate_id, verdict=verdict, score=score,
                           documents=doc_reports, candidate_signals=cand_signals,
                           modules=results, intake_issues=intake_issues)
