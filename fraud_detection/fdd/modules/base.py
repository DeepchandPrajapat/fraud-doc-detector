"""Contract every fraud module (F1, F2, ... F12) implements, plus the registry.

Adding a module = subclass FraudModule, set fraud_id/applies_to/scope, implement
`run`, decorate with @register. The pipeline handles skipping, errors and ordering.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Literal

from fdd.schemas import CandidateProfile, DocType, DocumentObject, ModuleResult, ModuleStatus


class FraudModule(ABC):
    fraud_id: ClassVar[str]
    name: ClassVar[str]
    applies_to: ClassVar[set[DocType]]
    # "document": run once per applicable document (Stage 4)
    # "candidate": run once with all documents (Stage 5)
    scope: ClassVar[Literal["document", "candidate"]]

    @abstractmethod
    def run(self, docs: list[DocumentObject], profile: CandidateProfile) -> ModuleResult:
        """`docs` holds one document for document-scope modules, all applicable docs otherwise."""

    def skipped(self, reason: str) -> ModuleResult:
        return ModuleResult(fraud_id=self.fraud_id, status=ModuleStatus.SKIPPED,
                            detail={"reason": reason})


REGISTRY: list[type[FraudModule]] = []


def register(cls: type[FraudModule]) -> type[FraudModule]:
    REGISTRY.append(cls)
    return cls
