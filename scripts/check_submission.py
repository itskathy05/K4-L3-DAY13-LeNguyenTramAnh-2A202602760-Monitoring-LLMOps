"""Run repeatable lab gates without exposing secret or PII values."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.pii import PII_PATTERNS

TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".html"}
SECRET_PATTERNS = [
    re.compile(r"\b(?:sk-lf|pk-lf)-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b(?:sk-proj|sk-or-v1|sk-ant)-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b(?:LANGFUSE_SECRET_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY)\s*=\s*['\"]?[A-Za-z0-9_-]{12,}\b", re.I),
]
PII_DETECTORS = [re.compile(pattern) for pattern in PII_PATTERNS.values()]
# These tracked lab fixtures/tests intentionally contain synthetic PII inputs.
PII_FIXTURE_ALLOWLIST = {
    "data/sample_queries.jsonl",
    "tests/test_observability_end_to_end.py",
    "tests/test_pii.py",
    "tests/test_validate_logs.py",
}
EVIDENCE_LINK = re.compile(r"evidence/[A-Za-z0-9_.-]+")
REQUIRED_SCREENSHOTS = (
    "04-structured-log.png", "05-pii-redaction.png", "06-trace-list.jpg",
    "07-trace-waterfall.jpg", "08-trace-metadata.jpg", "09-prompt-versions.jpg",
    "10-prompt-rollback.jpg", "12-incident-metric.png", "13-incident-log.png",
    "14-incident-trace.jpg",
)


def candidate_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    paths = []
    for name in result.stdout.splitlines():
        path = (REPO_ROOT / name).resolve()
        if path.is_file() and path.is_relative_to(REPO_ROOT) and path.suffix.lower() in TEXT_SUFFIXES:
            paths.append(path)
    return paths


def scan_files(paths: list[Path]) -> list[str]:
    findings = []
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        label = path.relative_to(REPO_ROOT).as_posix()
        for line_number, line in enumerate(lines, 1):
            if any(pattern.search(line) for pattern in SECRET_PATTERNS):
                findings.append(f"{label}:{line_number}: possible credential")
            if label not in PII_FIXTURE_ALLOWLIST and any(pattern.search(line) for pattern in PII_DETECTORS):
                findings.append(f"{label}:{line_number}: possible PII")
    return findings


def missing_evidence_links(report: Path) -> list[str]:
    text = report.read_text(encoding="utf-8")
    return sorted({link for link in EVIDENCE_LINK.findall(text) if not (report.parent / link).is_file()})


def run_gate(args: list[str], *, log_score: bool = False) -> bool:
    print("RUN", " ".join(args))
    result = subprocess.run(
        args, cwd=REPO_ROOT, check=False, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        return False
    if log_score:
        match = re.search(r"Estimated Score: (\d+)/100", result.stdout)
        return bool(match and int(match.group(1)) >= 80)
    return True


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-only", action="store_true", help="Scan tracked and candidate submission files only")
    args = parser.parse_args()
    findings = scan_files(candidate_paths())
    for finding in findings:
        print("FAIL", finding)
    if not findings:
        print("PASS credential/PII text scan")
    if args.scan_only:
        return int(bool(findings))

    missing = missing_evidence_links(REPO_ROOT / "submission" / "REPORT.md")
    for link in missing:
        print("FAIL missing evidence", link)
    missing_screenshots = [
        name for name in REQUIRED_SCREENSHOTS
        if not (REPO_ROOT / "submission" / "evidence" / name).is_file()
    ]
    for name in missing_screenshots:
        print("FAIL required runtime screenshot", name)
    passed = all([
        run_gate([sys.executable, "-m", "pytest", "-q"]),
        run_gate([sys.executable, "scripts/validate_logs.py"], log_score=True),
        run_gate([sys.executable, "scripts/validate_dashboard.py"]),
    ])
    return int(bool(findings or missing or missing_screenshots) or not passed)


if __name__ == "__main__":
    raise SystemExit(main())
