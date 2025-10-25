from __future__ import annotations

from app.policy import lint_policy


def test_policy_lint_blocks_wildcards():
    policy = {
        "Version": "2012-10-17",
        "Statement": {
            "Effect": "Allow",
            "Action": ["s3:*"],
            "Resource": "*",
        },
    }
    result = lint_policy(policy)
    assert not result.valid
    assert any("Wildcard actions" in finding.message for finding in result.findings)
    assert any("Wildcard resource" in finding.message for finding in result.findings)


def test_policy_lint_allows_break_glass():
    policy = {
        "Statement": {
            "Effect": "Allow",
            "Action": "*",
            "Resource": "*",
        }
    }
    result = lint_policy(policy, justification="Please BREAKGLASS for prod fix")
    assert result.valid
    assert all(finding.severity == "break-glass" for finding in result.findings)
