"""Modelli dati condivisi dal motore diagnostico."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List


class Status(str, Enum):
    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"          # il controllo non è riuscito a essere eseguito
    UNSUPPORTED = "unsupported"  # non disponibile su questo sistema operativo

    @property
    def label(self) -> str:
        return {
            Status.OK: "OK",
            Status.INFO: "Info",
            Status.WARNING: "Attenzione",
            Status.CRITICAL: "Critico",
            Status.ERROR: "Errore",
            Status.UNSUPPORTED: "Non disponibile",
        }[self]

    @property
    def icon(self) -> str:
        return {
            Status.OK: "✅",
            Status.INFO: "ℹ",
            Status.WARNING: "⚠",
            Status.CRITICAL: "✖",
            Status.ERROR: "❗",
            Status.UNSUPPORTED: "–",
        }[self]

    @property
    def weight(self) -> int:
        """Peso usato per il calcolo del punteggio di salute (più alto = peggio)."""
        return {
            Status.OK: 0,
            Status.INFO: 0,
            Status.UNSUPPORTED: 0,
            Status.ERROR: 1,
            Status.WARNING: 2,
            Status.CRITICAL: 5,
        }[self]


@dataclass
class CheckResult:
    check_id: str
    title: str
    status: Status
    summary: str
    details: List[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class CheckMeta:
    id: str
    label: str
    description: str
    default_selected: bool = True


@dataclass
class Category:
    id: str
    label: str
    icon: str
    checks: List[CheckMeta]


CheckFunction = Callable[[], CheckResult]
