import logging

from app.normalizer import NormalizedMessage
from app.rules.models import Rule
from app.rules.operators import evaluate_condition

logger = logging.getLogger(__name__)


class RuleEngine:
    def __init__(self, rules: list[Rule]) -> None:
        self._rules = sorted(
            (r for r in rules if r.enabled),
            key=lambda r: r.priority,
        )
        logger.info("RuleEngine loaded %d rule(s)", len(self._rules))

    def match(self, msg: NormalizedMessage) -> list[Rule]:
        """Return all rules that match the message, respecting priority and continue flag."""
        matched: list[Rule] = []
        for rule in self._rules:
            if self._matches(rule, msg):
                matched.append(rule)
                if not rule.continue_:
                    break
        return matched

    def _matches(self, rule: Rule, msg: NormalizedMessage) -> bool:
        if not rule.conditions:
            return True  # empty conditions = catch-all
        try:
            return evaluate_condition(rule.conditions, msg)
        except Exception as exc:
            logger.error("Error evaluating rule '%s': %s", rule.name, exc)
            return False
