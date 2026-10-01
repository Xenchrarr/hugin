from __future__ import annotations

import copy
import importlib
import pkgutil
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,119}$")


@dataclass(frozen=True)
class Observation:
    source_event_id: str
    occurred_at: datetime
    signals: frozenset[str]
    correlation_key: str | None = None
    attributes: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.source_event_id or not self.signals:
            raise ValueError("Observation requires source_event_id and signals")
        if self.occurred_at.tzinfo is None:
            raise ValueError("Observation occurred_at must be timezone-aware")


@dataclass(frozen=True)
class PollResult:
    observations: tuple[Observation, ...] = ()
    checkpoint: dict = field(default_factory=dict)
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class MonitorPollContext:
    monitor_key: str
    now: datetime
    checkpoint: dict = field(default_factory=dict)


@dataclass(frozen=True)
class IncidentCandidate:
    dedupe_key: str
    first_seen_at: datetime
    last_seen_at: datetime
    correlation_key: str | None = None
    incident_type: str | None = None
    response_workflow: str | None = None
    evidence: tuple[Observation, ...] = ()

    def workflow_input(self, incident_id) -> dict:
        return {"incident_id": str(incident_id), "evidence": [
            {"source_event_id": item.source_event_id, "occurred_at": item.occurred_at.isoformat(),
             "signals": sorted(item.signals), "correlation_key": item.correlation_key,
             "attributes": item.attributes, "evidence": item.evidence} for item in self.evidence]}


@dataclass(frozen=True)
class MonitorDefinition:
    key: str
    version: int
    interval_seconds: int
    source: str
    source_config: dict
    evaluator: str
    evaluator_config: dict
    response_workflow: str
    description: str = ""
    enabled: bool = True

    @property
    def observation_window_seconds(self):
        return int(self.evaluator_config.get("within_seconds", self.interval_seconds))

    def to_dict(self):
        return {name: copy.deepcopy(getattr(self, name)) for name in
                ("key", "version", "interval_seconds", "source", "source_config", "evaluator",
                 "evaluator_config", "response_workflow", "description", "enabled")}


class _Registry:
    def __init__(self): self.items = {}
    def get(self, key): return self.items.get(key)
    def list(self): return [self.items[key] for key in sorted(self.items)]


class SourceRegistry(_Registry):
    def register(self, key: str, poll: Callable, validate_config=None):
        _validate_key(key)
        if key in self.items: raise ValueError(f"Monitor source already registered: {key}")
        self.items[key] = type("Source", (), {"key": key, "poll": staticmethod(poll),
                                              "validate_config": staticmethod(validate_config) if validate_config else None})()
        return self.items[key]


class EvaluatorRegistry(_Registry):
    def register(self, key: str, evaluate: Callable, validate_config=None):
        _validate_key(key)
        if key in self.items: raise ValueError(f"Monitor evaluator already registered: {key}")
        self.items[key] = type("Evaluator", (), {"key": key, "evaluate": staticmethod(evaluate),
                                                  "validate_config": staticmethod(validate_config) if validate_config else None})()
        return self.items[key]


class MonitorRegistry(_Registry):
    def register(self, definition: MonitorDefinition):
        _validate_key(definition.key)
        if definition.key in self.items: raise ValueError(f"Monitor already registered: {definition.key}")
        if monitor_source_registry.get(definition.source) is None: raise ValueError(f"Unknown source: {definition.source}")
        if monitor_evaluator_registry.get(definition.evaluator) is None: raise ValueError(f"Unknown evaluator: {definition.evaluator}")
        if definition.version < 1 or definition.interval_seconds < 1: raise ValueError("Invalid monitor version or interval")
        source_definition=monitor_source_registry.get(definition.source)
        evaluator_definition=monitor_evaluator_registry.get(definition.evaluator)
        if source_definition.validate_config: source_definition.validate_config(definition.source_config)
        if evaluator_definition.validate_config: evaluator_definition.validate_config(definition.evaluator_config)
        if definition.observation_window_seconds < 1: raise ValueError("Monitor observation window must be positive")
        self.items[definition.key] = definition; return definition


def _validate_key(key):
    if not isinstance(key, str) or not _KEY.fullmatch(key): raise ValueError(f"Invalid monitor key: {key}")


monitor_source_registry = SourceRegistry()
monitor_evaluator_registry = EvaluatorRegistry()
monitor_registry = MonitorRegistry()


def source(key: str, *, validate_config=None):
    return lambda fn: (monitor_source_registry.register(key, fn, validate_config), fn)[1]


def evaluator(key: str, *, validate_config=None):
    return lambda fn: (monitor_evaluator_registry.register(key, fn, validate_config), fn)[1]


def monitor(**kwargs):
    return monitor_registry.register(MonitorDefinition(**kwargs))


@evaluator("core.each_observation")
def each_observation(observations: list[Observation], config: dict):
    signal = config.get("signal")
    return [IncidentCandidate(
        dedupe_key=item.correlation_key or item.source_event_id,
        correlation_key=item.correlation_key,
        incident_type=signal,
        first_seen_at=item.occurred_at,
        last_seen_at=item.occurred_at,
        evidence=(item,),
    ) for item in observations if signal is None or signal in item.signals]


def _validate_all_signals_config(config: dict) -> None:
    signals = config.get("required_signals")
    if (not isinstance(signals, list) or len(signals) < 2
            or any(not isinstance(item, str) or not item.strip() for item in signals)
            or len(set(signals)) != len(signals)):
        raise ValueError("required_signals must contain at least two unique signal names")
    seconds = config.get("within_seconds")
    if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds < 1:
        raise ValueError("within_seconds must be a positive integer")
    if not isinstance(config.get("distinct_observations", True), bool):
        raise ValueError("distinct_observations must be boolean")


def _signal_assignment(signals, candidates, distinct, selected=(), used=frozenset()):
    if not signals:
        return selected
    signal = signals[0]
    for observation in candidates[signal]:
        if distinct and observation.source_event_id in used:
            continue
        match = _signal_assignment(
            signals[1:], candidates, distinct,
            (*selected, observation), used | {observation.source_event_id})
        if match is not None:
            return match
    return None


@evaluator("core.all_signals_by_correlation", validate_config=_validate_all_signals_config)
def all_signals_by_correlation(observations: list[Observation], config: dict):
    """Match an unordered signal set in a bounded correlation-key window."""
    _validate_all_signals_config(config)
    required = tuple(config["required_signals"])
    window = timedelta(seconds=config["within_seconds"])
    distinct = config.get("distinct_observations", True)
    groups = defaultdict(list)
    for observation in observations:
        if observation.correlation_key:
            groups[observation.correlation_key].append(observation)
    incidents = []
    for correlation_key, group in groups.items():
        ordered = sorted(group, key=lambda item: (item.occurred_at, item.source_event_id))
        start = 0
        evidence = None
        for end, latest in enumerate(ordered):
            cutoff = latest.occurred_at - window
            while start <= end and ordered[start].occurred_at < cutoff:
                start += 1
            current = ordered[start:end + 1]
            candidates = {
                signal: [item for item in current if signal in item.signals]
                for signal in required
            }
            if any(not items for items in candidates.values()):
                continue
            selected = _signal_assignment(
                sorted(required, key=lambda signal: len(candidates[signal])),
                candidates, distinct)
            if selected is not None:
                evidence = tuple(sorted(
                    {item.source_event_id: item for item in selected}.values(),
                    key=lambda item: (item.occurred_at, item.source_event_id)))
                break
        if evidence:
            incidents.append(IncidentCandidate(
                dedupe_key=correlation_key,
                correlation_key=correlation_key,
                incident_type="+".join(required),
                first_seen_at=evidence[0].occurred_at,
                last_seen_at=evidence[-1].occurred_at,
                evidence=evidence,
            ))
    return sorted(incidents, key=lambda item: (item.first_seen_at, item.dedupe_key))


def _ordered_checks(config: dict) -> list[dict]:
    checks = config.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("ordered check evaluator requires checks")
    parsed, seen = [], set()
    for value in checks:
        if not isinstance(value, dict):
            raise ValueError("ordered evaluator checks must be objects")
        key = value.get("key")
        if not isinstance(key, str) or not _KEY.fullmatch(key) or key in seen:
            raise ValueError("ordered evaluator check keys must be unique and valid")
        signals = value.get("required_signals")
        if signals is None and isinstance(value.get("events"), list):
            signals = [event.get("signal") if isinstance(event, dict) else None
                       for event in value["events"]]
        if (not isinstance(signals, list) or not signals
                or any(not isinstance(signal, str) or not signal.strip() for signal in signals)
                or len(set(signals)) != len(signals)):
            raise ValueError(f"check {key} requires unique signal names")
        seconds = value.get("within_seconds")
        if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds < 1:
            raise ValueError(f"check {key} within_seconds must be a positive integer")
        response = value.get("response_workflow")
        if response is not None and (not isinstance(response, str) or not _KEY.fullmatch(response)):
            raise ValueError(f"check {key} response_workflow is invalid")
        seen.add(key)
        parsed.append({"key": key, "signals": tuple(signals), "seconds": seconds,
                       "response_workflow": response})
    overall = config.get("within_seconds")
    if (not isinstance(overall, int) or isinstance(overall, bool)
            or overall < max(item["seconds"] for item in parsed)):
        raise ValueError("within_seconds must cover every ordered check window")
    return parsed


def _validate_ordered_checks_config(config: dict) -> None:
    _ordered_checks(config)


def _ordered_evidence(observations, signals, window, signal_index=0,
                      observation_index=0, selected=()):
    if signal_index == len(signals):
        return selected
    for index in range(observation_index, len(observations)):
        observation = observations[index]
        if signals[signal_index] not in observation.signals:
            continue
        if selected and observation.source_event_id == selected[-1].source_event_id:
            continue
        if selected and observation.occurred_at - selected[0].occurred_at > window:
            break
        match = _ordered_evidence(
            observations, signals, window, signal_index + 1, index + 1,
            (*selected, observation))
        if match is not None:
            return match
    return None


@evaluator("core.ordered_checks_by_correlation", validate_config=_validate_ordered_checks_config)
def ordered_checks_by_correlation(observations: list[Observation], config: dict):
    """Match configured signal sequences independently for each correlation key."""
    checks = _ordered_checks(config)
    groups = defaultdict(list)
    for observation in observations:
        if observation.correlation_key:
            groups[observation.correlation_key].append(observation)
    incidents = []
    for check in checks:
        scoped = tuple(f"{check['key']}.{signal}" for signal in check["signals"])
        for correlation_key, group in groups.items():
            def order(item):
                evidence = item.evidence if isinstance(item.evidence, dict) else {}
                entry = evidence.get("archive_entry_number")
                if not isinstance(entry, int) or isinstance(entry, bool):
                    entry = 2**63 - 1
                return (item.occurred_at, str(evidence.get("archive_file", "")).casefold(),
                        entry, item.source_event_id)
            ordered = sorted(group, key=order)
            evidence = _ordered_evidence(
                ordered, scoped, timedelta(seconds=check["seconds"]))
            if evidence:
                incidents.append(IncidentCandidate(
                    dedupe_key=f"{check['key']}:{correlation_key}",
                    correlation_key=correlation_key,
                    incident_type=check["key"],
                    response_workflow=check["response_workflow"],
                    first_seen_at=evidence[0].occurred_at,
                    last_seen_at=evidence[-1].occurred_at,
                    evidence=evidence,
                ))
    return sorted(incidents, key=lambda item: (item.first_seen_at, item.dedupe_key))


@source("core.http_health")
def http_health(context: MonitorPollContext, config: dict) -> PollResult:
    """Emit an incident observation when a configured HTTP endpoint is unhealthy."""
    import requests

    url=config.get("url")
    if not isinstance(url,str) or not url.startswith(("http://","https://")):
        raise ValueError("core.http_health requires an http(s) url")
    timeout=max(0.1,float(config.get("timeout_seconds",10)))
    expected=int(config.get("expected_status",200))
    try:
        response=requests.get(url,timeout=timeout)
        if response.status_code==expected:return PollResult(checkpoint={"last_status":response.status_code})
        detail=f"HTTP {response.status_code}, expected {expected}"
    except requests.RequestException as exc:
        detail=str(exc)
    observation=Observation(
        source_event_id=f"{context.now.isoformat()}:{url}", occurred_at=context.now,
        signals=frozenset({"http_unhealthy"}), correlation_key=url,
        attributes={"url":url}, evidence={"error":detail},
    )
    return PollResult(observations=(observation,),checkpoint={"last_error":detail})


def discover_monitors() -> None:
    prefix=f"{__name__}.definitions."
    try:
        package=importlib.import_module(f"{__name__}.definitions")
    except ModuleNotFoundError:
        return
    for module in pkgutil.walk_packages(package.__path__,prefix):
        importlib.import_module(module.name)


discover_monitors()
