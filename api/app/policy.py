from __future__ import annotations

from typing import Iterable, List

from .config import get_settings
from .schemas import PolicyFinding, PolicyLintResponse


FORBIDDEN_WILDCARDS = {"*", "iam:*"}


def _find_wildcards(actions: Iterable[str]) -> List[str]:
    return [action for action in actions if action in FORBIDDEN_WILDCARDS or action.endswith(":*")]


def lint_policy(policy: dict, justification: str | None = None) -> PolicyLintResponse:
    findings: List[PolicyFinding] = []
    statements = policy.get("Statement", [])
    if not isinstance(statements, list):
        statements = [statements]

    for idx, stmt in enumerate(statements):
        actions = stmt.get("Action", [])
        resources = stmt.get("Resource", [])
        if isinstance(actions, str):
            actions = [actions]
        if isinstance(resources, str):
            resources = [resources]

        wildcard_actions = _find_wildcards(actions)
        if wildcard_actions:
            findings.append(
                PolicyFinding(
                    severity="high",
                    message=f"Wildcard actions not allowed: {', '.join(wildcard_actions)}",
                    path=f"Statement[{idx}].Action",
                )
            )
        if "*" in resources:
            findings.append(
                PolicyFinding(
                    severity="high",
                    message="Wildcard resource is not allowed",
                    path=f"Statement[{idx}].Resource",
                )
            )

    valid = not findings
    settings = get_settings()
    if findings and justification:
        keyword = settings.break_glass_keyword.upper()
        if keyword in justification.upper():
            valid = True
            for finding in findings:
                finding.severity = "break-glass"
    return PolicyLintResponse(valid=valid, findings=findings)
