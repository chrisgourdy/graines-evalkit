"""Project configuration (``evalkit.yaml``) and scenario loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, ValidationError

from evalkit.contracts import ContractModel, Scenario
from evalkit.governance.policy import AutonomyConfig


class AgentConfig(ContractModel):
    adapter: str = Field(description="Registered adapter id, e.g. 'sim.deterministic'.")
    version: str = Field(description="Agent version under test.")
    params: dict[str, Any] = Field(default_factory=dict)


class ProjectConfig(ContractModel):
    project_id: str
    name: str | None = None
    agents: dict[str, AgentConfig]
    scenarios_dir: str = "scenarios"
    weights: dict[str, float] = Field(
        default_factory=dict, description="Optional per-dimension weights (docs/SCORING.md)."
    )
    autonomy: AutonomyConfig = Field(
        default_factory=AutonomyConfig,
        description="docs/AUTONOMY_POLICY.md — max level, perimeter.",
    )


class ScenarioLoadError(ValueError):
    pass


def load_project(project_dir: Path) -> ProjectConfig:
    path = Path(project_dir) / "evalkit.yaml"
    if not path.is_file():
        msg = f"no evalkit.yaml in {project_dir}"
        raise ScenarioLoadError(msg)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return ProjectConfig.model_validate(data)
    except (ValidationError, yaml.YAMLError) as exc:
        msg = f"{path}: {exc}"
        raise ScenarioLoadError(msg) from exc


def load_scenarios(project_dir: Path, config: ProjectConfig) -> list[Scenario]:
    """Load and validate every ``*.yaml``/``*.yml``/``*.json`` scenario file.

    Fails loudly on the first invalid file: an invalid scenario never silently disappears.
    """
    root = Path(project_dir) / config.scenarios_dir
    if not root.is_dir():
        msg = f"scenarios directory not found: {root}"
        raise ScenarioLoadError(msg)
    scenarios: list[Scenario] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(p for p in root.rglob("*") if p.suffix in {".yaml", ".yml", ".json"}):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            scenario = Scenario.model_validate(raw)
        except (ValidationError, yaml.YAMLError) as exc:
            msg = f"{path}: {exc}"
            raise ScenarioLoadError(msg) from exc
        if scenario.project_id != config.project_id:
            msg = f"{path}: project_id {scenario.project_id!r} != {config.project_id!r}"
            raise ScenarioLoadError(msg)
        if scenario.agent_id not in config.agents:
            msg = f"{path}: unknown agent {scenario.agent_id!r}"
            raise ScenarioLoadError(msg)
        key = (scenario.scenario_id, scenario.version)
        if key in seen:
            msg = f"{path}: duplicate scenario {key}"
            raise ScenarioLoadError(msg)
        seen.add(key)
        scenarios.append(scenario)
    return scenarios
