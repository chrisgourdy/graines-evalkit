"""CLAUDE.md is the canonical index: every file it references must exist, and the mandatory
documents and sections must be present. Acceptance scenario #29 relies on this test."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLAUDE_MD = ROOT / "CLAUDE.md"

MANDATORY_FILES = [
    "README.md",
    "CLAUDE.md",
    "CHANGELOG.md",
    "pyproject.toml",
    "docs/ARCHITECTURE.md",
    "docs/EVALUATION_PROTOCOL.md",
    "docs/STATISTICAL_METHODS.md",
    "docs/METRICS.md",
    "docs/TOKEN_ACCOUNTING.md",
    "docs/COST_CONTROL.md",
    "docs/SCORING.md",
    "docs/OBSERVABILITY.md",
    "docs/ADAPTER_SPEC.md",
    "docs/SECURITY.md",
    "docs/AUTONOMY_POLICY.md",
    "docs/DISTRIBUTION.md",
    "docs/RELEASE_POLICY.md",
    "docs/ROADMAP.md",
    "docs/BACKLOG.md",
    "docs/LEARNINGS.md",
    "docs/RUNBOOK.md",
    "docs/CONTRIBUTING.md",
    "docs/STATUS.md",
    "docs/ACCEPTANCE_SCENARIOS.md",
    "docs/SPEC_MASTER_PROMPT_V2.1.md",
    "docs/TUTORIEL.md",
    "docs/ACCEPTANCE_REPORT.md",
    "docs/RELEASE_CHECKLIST.md",
]

MANDATORY_SECTIONS = [
    "## 1. Purpose",
    "## 2. Project state",
    "## 3. Architecture",
    "## 4. Contracts",
    "## 5. Conventions",
    "## 6. Commands",
    "## 7. Documentation map",
    "## 8. Security and autonomy rules",
    "## 9. Resume procedure",
    "## 10. Next actions",
]

_REF = re.compile(
    r"`((?:docs/|src/|tests/|scenarios/|sdk/)[^`\s]*|[A-Za-z0-9_.-]+\.(?:md|toml|yml|yaml))`"
)


@pytest.mark.parametrize("rel", MANDATORY_FILES)
def test_mandatory_file_exists(rel: str) -> None:
    assert (ROOT / rel).is_file(), f"mandatory file missing: {rel}"


@pytest.mark.parametrize("section", MANDATORY_SECTIONS)
def test_claude_md_has_section(section: str) -> None:
    assert section in CLAUDE_MD.read_text(encoding="utf-8"), f"CLAUDE.md lacks {section!r}"


def _referenced_paths(text: str) -> set[str]:
    refs: set[str] = set()
    for match in _REF.finditer(text):
        ref = match.group(1)
        if ref.endswith("/") or "*" in ref or "<" in ref:
            continue
        refs.add(ref)
    return refs


def test_claude_md_references_exist() -> None:
    text = CLAUDE_MD.read_text(encoding="utf-8")
    missing = sorted(r for r in _referenced_paths(text) if not (ROOT / r).exists())
    assert not missing, f"CLAUDE.md references missing paths: {missing}"


def test_adrs_exist_and_numbered() -> None:
    adrs = sorted((ROOT / "docs" / "adr").glob("*.md"))
    assert adrs, "no ADR found"
    numbers = [int(p.name[:4]) for p in adrs]
    assert numbers == list(range(1, len(numbers) + 1)), "ADR numbering has gaps"
    for p in adrs:
        head = p.read_text(encoding="utf-8").splitlines()[0]
        assert head.startswith("# ADR-"), f"{p.name} lacks ADR title"


def test_module_packages_have_docstring() -> None:
    pkg = ROOT / "src" / "evalkit"
    for init in sorted(pkg.glob("*/__init__.py")):
        text = init.read_text(encoding="utf-8").lstrip()
        assert text.startswith('"""'), (
            f"{init.parent.name}/__init__.py must state its responsibility"
        )


def test_version_consistency() -> None:
    import evalkit

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{evalkit.__version__}"' in pyproject
    assert f"**Version:** {evalkit.__version__}" in CLAUDE_MD.read_text(encoding="utf-8")
