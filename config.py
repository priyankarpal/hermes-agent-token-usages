"""Config loading for the token-usage plugin.

All user-facing strings are config-driven
(token_plugin.* in ~/.hermes/config.yaml, or TOKEN_PLUGIN_* environment
variables); there are no hardcoded UI strings in this module.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

try:
    import yaml  # Hermes runtime dependency
except Exception:  # pragma: no cover - stdlib fallback only
    yaml = None

# Config keys (the only hardcoded names; all UI text is config-driven)
CONFIG_SECTION = "token_plugin"
ENV_PREFIX = "TOKEN_PLUGIN_"
WINDOWS = ("lifetime", "7d", "30d", "90d")
FORMATS = ("table", "json")


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))


def _config_file() -> Path:
    return _hermes_home() / "config.yaml"


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    return _naive_yaml(text)


def _naive_yaml(text: str) -> dict[str, Any]:
    """Tiny indentation-based YAML subset parser (2-3 levels).

    Handles the flat/nested config we need (``token_plugin:`` → ``labels:`` →
    ``hdr_db: ...``) without PyYAML.
    """
    data: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, data)]

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if ":" not in stripped:
            continue
        key, _, val = stripped.partition(":")
        key = key.strip()
        val = val.strip()
        while len(stack) > 1 and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        if val == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = val.strip('"').strip("'")
    return data


def _coerce_env(value: str) -> Any:
    low = value.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _set_nested(data: dict[str, Any], keys: list[str], value: Any) -> None:
    for k in keys[:-1]:
        data = data.setdefault(k, {})
    data[keys[-1]] = value


def _get_nested(data: Any, keys: list[str], default: Any = None) -> Any:
    cur: Any = data
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def load_config() -> dict[str, Any]:
    """token_plugin config: config.yaml values overlaid by TOKEN_PLUGIN_* env vars."""
    raw = _load_yaml_file(_config_file())
    tp = _get_nested(raw, [CONFIG_SECTION], {}) or {}
    if not isinstance(tp, dict):
        tp = {}
    cfg: dict[str, Any] = {CONFIG_SECTION: dict(tp)}
    for env_key, value in os.environ.items():
        if not env_key.startswith(ENV_PREFIX):
            continue
        suffix = env_key[len(ENV_PREFIX):]
        if suffix:
            _set_nested(cfg, [CONFIG_SECTION, suffix.lower()], _coerce_env(value))
    return cfg


def label(cfg: dict[str, Any], key: str) -> str:
    """User-facing label from config; falls back to the key itself."""
    val = _get_nested(cfg, [CONFIG_SECTION, "labels", key], None)
    return val if val is not None else key


def cfg_val(cfg: dict[str, Any], key: str, default: Any = None) -> Any:
    return _get_nested(cfg, [CONFIG_SECTION, key], default)
