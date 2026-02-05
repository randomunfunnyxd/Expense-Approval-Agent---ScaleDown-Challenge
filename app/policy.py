from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

POLICY_PATH = Path("policy.yaml")


def load_policy() -> Dict[str, Any]:
    if not POLICY_PATH.exists():
        raise FileNotFoundError("policy.yaml not found")
    with POLICY_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("policy.yaml must be a mapping")
    return data
