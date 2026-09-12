"""Motore di esecuzione dei controlli diagnostici, punteggio di salute e generazione report."""
from __future__ import annotations

import datetime
import time
from typing import Callable, Dict, List, Optional

from . import checks_hardware as hw
from . import checks_problems as pb
from . import checks_software as sw
from .catalog import CATEGORIES, find_check_meta
from .models import CheckResult, Status

CHECK_FUNCTIONS: Dict[str, Callable[[], CheckResult]] = {
    # Hardware
    "cpu": hw.check_cpu,
    "ram": hw.check_ram,
    "disk": hw.check_disk,
    "disk_health": hw.check_disk_health,
    "gpu": hw.check_gpu,
    "motherboard": hw.check_motherboard,
    "network_hw": hw.check_network_hw,
    "battery": hw.check_battery,
    "temperature": hw.check_temperature,
    "usb": hw.check_usb,
    "performance_monitor": hw.check_performance_monitor,
    "disk_speed_test": hw.check_disk_speed_test,
    # Software
    "os_info": sw.check_os_info,
    "windows_update": sw.check_windows_update,
    "installed_apps": sw.check_installed_apps,
    "startup_programs": sw.check_startup_programs,
    "running_processes": sw.check_running_processes,
    "antivirus": sw.check_antivirus,
    "drivers": sw.check_drivers,
    "services": sw.check_services,
    # Problemi potenziali
    "disk_space_alert": pb.check_disk_space_alert,
    "cpu_load_alert": pb.check_cpu_load_alert,
    "ram_pressure": pb.check_ram_pressure,
    "temp_alert": pb.check_temp_alert,
    "battery_health_alert": pb.check_battery_health_alert,
    "event_log_errors": pb.check_event_log_errors,
    "suspicious_processes": pb.check_suspicious_processes,
    "pending_reboot": pb.check_pending_reboot,
    "disk_fragmentation": pb.check_disk_fragmentation,
    "network_connectivity": pb.check_network_connectivity,
    "reliability_history": pb.check_reliability_history,
}


class DiagnosticEngine:
    def run_single(self, check_id: str) -> CheckResult:
        meta = find_check_meta(check_id)
        func = CHECK_FUNCTIONS.get(check_id)
        start = time.time()
        try:
            result = func() if func else CheckResult(check_id, meta.label, Status.ERROR, "Controllo non implementato")
        except Exception as exc:  # difesa: un controllo non deve mai far crashare l'app
            result = CheckResult(check_id, meta.label, Status.ERROR, f"Errore durante l'esecuzione: {exc}")
        result.duration_ms = (time.time() - start) * 1000
        return result

    def run_checks(
        self,
        selected_ids: List[str],
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> "Dict[str, CheckResult]":
        results: Dict[str, CheckResult] = {}
        total = len(selected_ids)
        for index, check_id in enumerate(selected_ids, start=1):
            if should_stop and should_stop():
                break
            meta = find_check_meta(check_id)
            if on_progress:
                on_progress(index, total, meta.label)
            results[check_id] = self.run_single(check_id)
        return results

    @staticmethod
    def compute_health_score(results: Dict[str, CheckResult]) -> int:
        if not results:
            return 100
        relevant = [r for r in results.values() if r.status not in (Status.UNSUPPORTED, Status.INFO)]
        if not relevant:
            return 100
        penalty = sum(r.status.weight for r in relevant)
        max_penalty = len(relevant) * Status.CRITICAL.weight
        score = 100 - int((penalty / max_penalty) * 100) if max_penalty else 100
        return max(0, min(100, score))

    @staticmethod
    def count_by_status(results: Dict[str, CheckResult]) -> Dict[Status, int]:
        counts = {s: 0 for s in Status}
        for r in results.values():
            counts[r.status] += 1
        return counts

    @staticmethod
    def generate_text_report(results: Dict[str, CheckResult], score: int) -> str:
        now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        lines = [
            "=" * 60,
            "  REPORT DIAGNOSTICO PC",
            f"  Generato il: {now}",
            f"  Punteggio di salute stimato: {score}/100",
            "=" * 60,
            "",
        ]
        for cat in CATEGORIES:
            cat_results = [results[c.id] for c in cat.checks if c.id in results]
            if not cat_results:
                continue
            lines.append(f"## {cat.icon} {cat.label}")
            lines.append("-" * 60)
            for r in cat_results:
                lines.append(f"[{r.status.label.upper()}] {r.title}: {r.summary}")
                for d in r.details:
                    lines.append(f"    {d}")
                lines.append("")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def generate_html_report(results: Dict[str, CheckResult], score: int) -> str:
        now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        color_map = {
            Status.OK: "#22c55e",
            Status.INFO: "#38bdf8",
            Status.WARNING: "#f59e0b",
            Status.CRITICAL: "#ef4444",
            Status.ERROR: "#f97316",
            Status.UNSUPPORTED: "#64748b",
        }
        sections = []
        for cat in CATEGORIES:
            cat_results = [results[c.id] for c in cat.checks if c.id in results]
            if not cat_results:
                continue
            rows = []
            for r in cat_results:
                details_html = "".join(f"<li>{d}</li>" for d in r.details)
                rows.append(
                    f"""
                    <div class="check">
                      <div class="check-head">
                        <span class="badge" style="background:{color_map[r.status]}">{r.status.label}</span>
                        <strong>{r.title}</strong>
                      </div>
                      <p class="summary">{r.summary}</p>
                      {f'<ul class="details">{details_html}</ul>' if r.details else ''}
                    </div>"""
                )
            sections.append(f"<h2>{cat.icon} {cat.label}</h2>" + "".join(rows))

        return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><title>Report Diagnostico PC</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; background:#0f172a; color:#e2e8f0; padding:32px; }}
  h1 {{ margin-bottom:4px; }}
  .meta {{ color:#94a3b8; margin-bottom:24px; }}
  .score {{ font-size:48px; font-weight:bold; color:#38bdf8; }}
  h2 {{ margin-top:32px; border-bottom:1px solid #334155; padding-bottom:8px; }}
  .check {{ background:#1e293b; border-radius:10px; padding:14px 18px; margin:10px 0; }}
  .check-head {{ display:flex; align-items:center; gap:10px; }}
  .badge {{ color:white; font-size:12px; padding:2px 10px; border-radius:999px; font-weight:600; }}
  .summary {{ margin:6px 0 0 0; color:#cbd5e1; }}
  .details {{ color:#94a3b8; font-size:13px; margin-top:8px; }}
</style></head>
<body>
  <h1>Report Diagnostico PC</h1>
  <div class="meta">Generato il {now}</div>
  <div class="score">{score}/100</div>
  {''.join(sections)}
</body></html>"""
