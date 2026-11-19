"""Domain model: entities and value objects.

Pure business concepts. No dependency on config, DB, CLI, or Hermes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# -- Value objects ----------------------------------------------------------

class Window:
    """Immutable time-window value object."""

    WINDOWS = ("lifetime", "7d", "30d", "90d")
    OFFSETS = {"7d": "-7 days", "30d": "-30 days", "90d": "-90 days"}

    def __init__(self, value: str) -> None:
        if value not in self.WINDOWS:
            raise ValueError(f"Unknown window: {value!r}")
        self._value = value

    @property
    def value(self) -> str:
        return self._value

    @property
    def offset(self) -> Optional[str]:
        return self.OFFSETS.get(self._value)

    @property
    def is_lifetime(self) -> bool:
        return self._value == "lifetime"

    def __str__(self) -> str:
        return self._value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Window) and self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)


class OutputFormat:
    """Immutable output-format value object."""

    FORMATS = ("table", "json")

    def __init__(self, value: str) -> None:
        if value not in self.FORMATS:
            raise ValueError(f"Unknown output format: {value!r}")
        self._value = value

    @property
    def value(self) -> str:
        return self._value

    @property
    def is_json(self) -> bool:
        return self._value == "json"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, OutputFormat) and self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)


class Currency:
    """Immutable currency label (no FX conversion)."""

    def __init__(self, label: str = "USD") -> None:
        self._label = label or "USD"

    @property
    def label(self) -> str:
        return self._label

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Currency) and self._label == other._label

    def __hash__(self) -> int:
        return hash(self._label)


# -- Entities ---------------------------------------------------------------

@dataclass(frozen=True)
class Session:
    """A single session roll-up from the ``sessions`` table."""

    id: str
    model: str
    started_at: Optional[float]
    last_activity_at: Optional[float]
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    api_call_count: int
    estimated_cost_usd: float
    actual_cost_usd: float
    total_tokens: int
    archived: int
    profile_name: Optional[str]

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Session":
        return cls(
            id=str(row["id"]),
            model=str(row.get("model", "") or ""),
            started_at=row.get("started_at"),
            last_activity_at=row.get("last_activity_at"),
            input_tokens=int(row.get("input_tokens") or 0),
            output_tokens=int(row.get("output_tokens") or 0),
            cache_read_tokens=int(row.get("cache_read_tokens") or 0),
            cache_write_tokens=int(row.get("cache_write_tokens") or 0),
            reasoning_tokens=int(row.get("reasoning_tokens") or 0),
            api_call_count=int(row.get("api_call_count") or 0),
            estimated_cost_usd=float(row.get("estimated_cost_usd") or 0),
            actual_cost_usd=float(row.get("actual_cost_usd") or 0),
            total_tokens=int(row.get("total_tokens") or 0),
            archived=int(row.get("archived") or 0),
            profile_name=row.get("profile_name"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "model": self.model,
            "started_at": self.started_at, "last_activity_at": self.last_activity_at,
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "api_call_count": self.api_call_count,
            "estimated_cost_usd": self.estimated_cost_usd,
            "actual_cost_usd": self.actual_cost_usd,
            "total_tokens": self.total_tokens, "archived": self.archived,
            "profile_name": self.profile_name,
        }


@dataclass(frozen=True)
class ModelUsage:
    """Aggregated usage for a single model."""

    model: str
    sessions: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    total_tokens: int
    api_calls: int
    est_cost: float
    actual_cost: float

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ModelUsage":
        return cls(
            model=str(row.get("model", "")),
            sessions=int(row.get("sessions") or 0),
            input_tokens=int(row.get("input_tokens") or 0),
            output_tokens=int(row.get("output_tokens") or 0),
            cache_read_tokens=int(row.get("cache_read_tokens") or 0),
            cache_write_tokens=int(row.get("cache_write_tokens") or 0),
            reasoning_tokens=int(row.get("reasoning_tokens") or 0),
            total_tokens=int(row.get("total_tokens") or 0),
            api_calls=int(row.get("api_calls") or 0),
            est_cost=float(row.get("est_cost") or 0),
            actual_cost=float(row.get("actual_cost") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model, "sessions": self.sessions,
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "total_tokens": self.total_tokens, "api_calls": self.api_calls,
            "est_cost": self.est_cost, "actual_cost": self.actual_cost,
        }


@dataclass(frozen=True)
class SessionModelUsageRow:
    """A single model/billing-context row within one session."""

    model: str
    billing_provider: Optional[str]
    billing_base_url: Optional[str]
    billing_mode: Optional[str]
    task: Optional[str]
    api_call_count: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    estimated_cost_usd: float
    actual_cost_usd: float
    first_seen: Optional[float]
    last_seen: Optional[float]

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "SessionModelUsageRow":
        return cls(
            model=str(row.get("model", "")),
            billing_provider=row.get("billing_provider"),
            billing_base_url=row.get("billing_base_url"),
            billing_mode=row.get("billing_mode"),
            task=row.get("task"),
            api_call_count=int(row.get("api_call_count") or 0),
            input_tokens=int(row.get("input_tokens") or 0),
            output_tokens=int(row.get("output_tokens") or 0),
            cache_read_tokens=int(row.get("cache_read_tokens") or 0),
            cache_write_tokens=int(row.get("cache_write_tokens") or 0),
            reasoning_tokens=int(row.get("reasoning_tokens") or 0),
            estimated_cost_usd=float(row.get("estimated_cost_usd") or 0),
            actual_cost_usd=float(row.get("actual_cost_usd") or 0),
            first_seen=row.get("first_seen"),
            last_seen=row.get("last_seen"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model, "billing_provider": self.billing_provider,
            "billing_base_url": self.billing_base_url, "billing_mode": self.billing_mode,
            "task": self.task, "api_call_count": self.api_call_count,
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "actual_cost_usd": self.actual_cost_usd,
            "first_seen": self.first_seen, "last_seen": self.last_seen,
        }


@dataclass
class UsageReport:
    """The full token-usage report aggregate."""

    totals: dict[str, Any]
    models: list
    sessions: list
    meta: dict[str, Any]
    session_mode: bool = False
    session_info: Optional[dict[str, Any]] = None
    session_models: list = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "totals": self.totals, "models": self.models,
            "sessions": self.sessions, "meta": self.meta,
            "session_mode": self.session_mode,
        }
        if self.session_mode:
            out["session"] = self.session_info
            out["session_models"] = self.session_models
        return out
