"""
Test plan: the (provider × model) matrix used by integration/e2e runs.

A plan can be loaded from a YAML or JSON file, or built ad hoc from CLI flags
(``--provider`` / ``--model``). It is serialised into the ``MTH_PLAN`` env var so
the pytest subprocess and its fixtures can rebuild the active target.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Union

from mangaba_test import compat

_PLAN_ENV = "MTH_PLAN"


@dataclass
class Target:
    """A single provider + model (model may be a list = OpenRouter fallback)."""

    provider: str
    model: Union[str, List[str]]
    api_key_env: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)

    @property
    def model_label(self) -> str:
        return self.model if isinstance(self.model, str) else " | ".join(self.model)

    @property
    def id(self) -> str:
        return f"{self.provider}:{self.model_label}"


@dataclass
class TestPlan:
    """A matrix of targets plus shared defaults and suite/module selection."""

    targets: List[Target] = field(default_factory=list)
    defaults: Dict[str, Any] = field(default_factory=dict)
    suites: List[str] = field(default_factory=list)
    modules: List[str] = field(default_factory=list)

    # -- construction ----------------------------------------------------

    @classmethod
    def single(
        cls,
        provider: str,
        model: Union[str, List[str]],
        *,
        api_key_env: Optional[str] = None,
        defaults: Optional[Dict[str, Any]] = None,
    ) -> "TestPlan":
        return cls(
            targets=[Target(provider=provider, model=model, api_key_env=api_key_env)],
            defaults=defaults or {},
        )

    @classmethod
    def from_file(cls, path: str) -> "TestPlan":
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
        return cls.from_dict(_parse(raw, path))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestPlan":
        defaults = data.get("defaults", {}) or {}
        targets: List[Target] = []
        for prov in data.get("providers", []):
            name = prov["name"]
            api_key_env = prov.get("api_key_env")
            options = {**defaults, **(prov.get("options", {}) or {})}
            for model in prov.get("models", []):
                targets.append(
                    Target(provider=name, model=model, api_key_env=api_key_env, options=dict(options))
                )
        return cls(
            targets=targets,
            defaults=defaults,
            suites=list(data.get("suites", []) or []),
            modules=list(data.get("modules", []) or []),
        )

    # -- validation ------------------------------------------------------

    def validate(self) -> List[str]:
        """Return a list of human-readable problems (empty = valid)."""
        problems: List[str] = []
        if not self.targets:
            problems.append("plan has no targets (no providers/models)")
        supported = None
        if compat.get_supported_providers is not None:
            try:
                supported = set(compat.get_supported_providers()) | {"mock", "fake", "dummy"}
            except Exception:
                supported = None
        if supported is not None:
            for t in self.targets:
                if t.provider.lower() not in supported:
                    problems.append(
                        f"provider '{t.provider}' not supported by mangaba "
                        f"v{compat.version or '?'} (known: {', '.join(sorted(supported))})"
                    )
        return problems

    # -- serialisation ---------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "targets": [asdict(t) for t in self.targets],
            "defaults": self.defaults,
            "suites": self.suites,
            "modules": self.modules,
        }

    def export_env(self) -> None:
        """Publish this plan to the environment for the pytest subprocess."""
        os.environ[_PLAN_ENV] = json.dumps(self.to_dict())

    @classmethod
    def from_env(cls) -> Optional["TestPlan"]:
        raw = os.getenv(_PLAN_ENV)
        if not raw:
            return None
        data = json.loads(raw)
        plan = cls(defaults=data.get("defaults", {}), suites=data.get("suites", []), modules=data.get("modules", []))
        plan.targets = [Target(**t) for t in data.get("targets", [])]
        return plan

    @property
    def primary(self) -> Optional[Target]:
        return self.targets[0] if self.targets else None


def _parse(raw: str, path: str) -> Dict[str, Any]:
    """Parse YAML if available/needed, else JSON. Keeps YAML an optional dep."""
    if path.endswith((".yaml", ".yml")):
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "PyYAML is required for .yaml plans (pip install pyyaml), "
                "or provide a .json plan instead."
            ) from exc
        return yaml.safe_load(raw) or {}
    return json.loads(raw)
