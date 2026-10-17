"""Strict policy parsing and fixed runner profiles for Phase 1B.

Policy files are untrusted input. This module accepts a deliberately small schema,
uses PyYAML's safe constructor, rejects YAML aliases/anchors and duplicate keys,
and never accepts user-defined commands or shell fragments.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode
from yaml.tokens import AliasToken, AnchorToken

MAX_POLICY_BYTES = 256 * 1024
MAX_TRUSTED_WORKFLOWS = 50
MAX_RUNNER_PROFILES = 10
MAX_HARNESS_PATHS = 100
MAX_OBLIGATIONS = 500
MAX_CLAIM_LENGTH = 2_000
MAX_SELECTOR_LENGTH = 240

_REQUIRED_HARNESS_PATHS = frozenset(
    {
        ".verification-policy.yml",
        ".github/workflows/",
        "conftest.py",
        "pytest.ini",
        "pyproject.toml",
        "package.json",
    }
)
_SEVERITIES = ("critical", "high", "medium", "low")
_OBLIGATION_ID_RE = re.compile(r"^OBL-[A-Z0-9][A-Z0-9-]{0,59}$")
_CATEGORY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SELECTOR_PATH_RE = re.compile(r"^[A-Za-z0-9_./-]+\.py$")
_NODE_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_WORKFLOW_RE = re.compile(r"^\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml$")


class PolicyValidationError(ValueError):
    """Raised when policy input is malformed or violates a security invariant."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate, non-string, and merge mapping keys."""

    def construct_mapping(self, node: Node, deep: bool = False) -> dict[str, object]:
        if not isinstance(node, MappingNode):
            raise PolicyValidationError("Expected a YAML mapping.")
        if any(
            isinstance(key_node, ScalarNode)
            and key_node.tag == "tag:yaml.org,2002:merge"
            for key_node, _ in node.value
        ):
            raise PolicyValidationError("YAML merge keys are not supported.")
        mapping: dict[str, object] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise PolicyValidationError("All YAML mapping keys must be strings (string keys only).")
            if key in mapping:
                raise PolicyValidationError(f"Duplicate YAML key: {key!r}.")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


@dataclass(frozen=True, slots=True)
class RunnerProfile:
    """A verifier-owned argv template; policy input may select but never redefine it."""

    name: str
    argv_prefix: tuple[str, ...]
    accepts_selector: bool


@dataclass(frozen=True, slots=True)
class SeverityRule:
    """Policy-level blocking and human-governance settings for one severity."""

    severity: str
    blocking: bool
    human_approval_allowed: bool


@dataclass(frozen=True, slots=True)
class ObligationRule:
    """Declarative verification obligation loaded from trusted-base policy."""

    obligation_id: str
    category: str
    severity: str
    claim: str
    runner_profile: str
    selector: str


@dataclass(frozen=True, slots=True)
class VerificationPolicy:
    """Validated immutable policy. It contains no executable user-supplied commands."""

    version: int
    trusted_workflows: tuple[str, ...]
    runner_profiles: tuple[str, ...]
    severity_rules: tuple[SeverityRule, ...]
    harness_sensitive_paths: tuple[str, ...]
    obligations: tuple[ObligationRule, ...]

    def severity_rule(self, severity: str) -> SeverityRule:
        """Return the rule for a known severity, or raise a policy error."""
        for rule in self.severity_rules:
            if rule.severity == severity:
                return rule
        raise PolicyValidationError(f"No severity rule configured for {severity!r}.")


RUNNER_PROFILES: dict[str, RunnerProfile] = {
    "pytest_targeted": RunnerProfile(
        name="pytest_targeted",
        argv_prefix=(sys.executable, "-m", "pytest", "--no-header", "--tb=short", "-q"),
        accepts_selector=True,
    ),
    "pytest_full": RunnerProfile(
        name="pytest_full",
        argv_prefix=(sys.executable, "-m", "pytest", "--no-header", "--tb=short", "-q", "tests"),
        accepts_selector=False,
    ),
}


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise PolicyValidationError(f"{field} must be a mapping.")
    if any(not isinstance(key, str) for key in value):
        raise PolicyValidationError(f"{field} must use string keys.")
    return value


def _exact_keys(
    value: dict[str, object], *, field: str, required: set[str]
) -> None:
    actual = set(value)
    missing = required - actual
    unknown = actual - required
    if missing:
        raise PolicyValidationError(f"{field} is missing required key(s): {', '.join(sorted(missing))}.")
    if unknown:
        raise PolicyValidationError(f"{field} contains unknown key(s): {', '.join(sorted(unknown))}.")


def _string(value: object, field: str, *, max_length: int = 500) -> str:
    if not isinstance(value, str):
        raise PolicyValidationError(f"{field} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise PolicyValidationError(f"{field} must not be empty.")
    if len(normalized) > max_length:
        raise PolicyValidationError(f"{field} exceeds the {max_length}-character limit.")
    if "\x00" in normalized:
        raise PolicyValidationError(f"{field} must not contain NUL characters.")
    return normalized


def _string_list(
    value: object,
    field: str,
    *,
    max_items: int,
    allow_trailing_slash: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PolicyValidationError(f"{field} must be a list.")
    if not value:
        raise PolicyValidationError(f"{field} must not be empty.")
    if len(value) > max_items:
        raise PolicyValidationError(f"{field} may contain at most {max_items} items.")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(_string(item, f"{field}[{index}]", max_length=300))
    if len(set(result)) != len(result):
        raise PolicyValidationError(f"{field} must not contain duplicates.")
    if not allow_trailing_slash and any(item.endswith("/") for item in result):
        raise PolicyValidationError(f"{field} entries must not end with '/'.")
    return tuple(result)


def _validate_repo_relative_path(value: str, field: str, *, allow_prefix: bool = False) -> None:
    candidate = value[:-1] if allow_prefix and value.endswith("/") else value
    path = PurePosixPath(candidate)
    if (
        not candidate
        or path.is_absolute()
        or "\\" in candidate
        or any(part in {"", ".", ".."} for part in candidate.split("/"))
        or candidate.startswith("-")
        or ":" in candidate
    ):
        raise PolicyValidationError(f"{field} must be a safe repository-relative path: {value!r}.")


def validate_test_selector(value: str) -> str:
    """Validate a deliberately narrow pytest node selector; never interpret shell syntax."""
    selector = _string(value, "selector", max_length=MAX_SELECTOR_LENGTH)
    if selector.startswith("-") or "\\" in selector or any(char.isspace() for char in selector):
        raise PolicyValidationError("selector contains a forbidden option, backslash, or whitespace.")
    pieces = selector.split("::")
    file_path = pieces[0]
    if not _SELECTOR_PATH_RE.fullmatch(file_path):
        raise PolicyValidationError("selector must start with a relative .py test file path.")
    _validate_repo_relative_path(file_path, "selector path")
    if len(PurePosixPath(file_path).parts) < 2:
        raise PolicyValidationError("selector must point inside a test subdirectory.")
    if len(pieces) > 1 and any(not _NODE_ID_RE.fullmatch(part) for part in pieces[1:]):
        raise PolicyValidationError("selector node names must be simple Python identifiers.")
    return selector


def _validate_trusted_workflow(value: str) -> str:
    if not _WORKFLOW_RE.fullmatch(value):
        raise PolicyValidationError(
            "trusted_workflows entries must be direct .github/workflows/*.yml or *.yaml paths."
        )
    _validate_repo_relative_path(value, "trusted workflow")
    return value


def _validate_sensitive_path(value: str) -> str:
    _validate_repo_relative_path(value, "harness_sensitive_paths entry", allow_prefix=True)
    return value


def _parse_severity_rules(value: object) -> tuple[SeverityRule, ...]:
    raw_rules = _mapping(value, "severity_rules")
    _exact_keys(raw_rules, field="severity_rules", required=set(_SEVERITIES))
    rules: list[SeverityRule] = []
    for severity in _SEVERITIES:
        raw = _mapping(raw_rules[severity], f"severity_rules.{severity}")
        _exact_keys(
            raw,
            field=f"severity_rules.{severity}",
            required={"blocking", "human_approval_allowed"},
        )
        blocking = raw["blocking"]
        human_allowed = raw["human_approval_allowed"]
        if type(blocking) is not bool or type(human_allowed) is not bool:
            raise PolicyValidationError(
                f"severity_rules.{severity} values must be booleans."
            )
        if severity in {"critical", "high"} and not blocking:
            raise PolicyValidationError(f"{severity} severity must remain blocking.")
        rules.append(
            SeverityRule(
                severity=severity,
                blocking=blocking,
                human_approval_allowed=human_allowed,
            )
        )
    return tuple(rules)


def _parse_obligations(value: object, allowed_profiles: tuple[str, ...]) -> tuple[ObligationRule, ...]:
    if not isinstance(value, list) or not value:
        raise PolicyValidationError("obligations must be a non-empty list.")
    if len(value) > MAX_OBLIGATIONS:
        raise PolicyValidationError(f"obligations may contain at most {MAX_OBLIGATIONS} items.")
    rules: list[ObligationRule] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(value):
        field = f"obligations[{index}]"
        raw = _mapping(item, field)
        _exact_keys(
            raw,
            field=field,
            required={"id", "category", "severity", "claim", "runner_profile", "selector"},
        )
        obligation_id = _string(raw["id"], f"{field}.id", max_length=64)
        if not _OBLIGATION_ID_RE.fullmatch(obligation_id):
            raise PolicyValidationError(f"{field}.id must match OBL-[A-Z0-9][A-Z0-9-]*.")
        if obligation_id in seen_ids:
            raise PolicyValidationError(f"Duplicate obligation id: {obligation_id}.")
        seen_ids.add(obligation_id)

        category = _string(raw["category"], f"{field}.category", max_length=64)
        if not _CATEGORY_RE.fullmatch(category):
            raise PolicyValidationError(f"{field}.category must be lowercase snake_case.")
        severity = _string(raw["severity"], f"{field}.severity", max_length=16)
        if severity not in _SEVERITIES:
            raise PolicyValidationError(f"{field}.severity must be one of {', '.join(_SEVERITIES)}.")
        claim = _string(raw["claim"], f"{field}.claim", max_length=MAX_CLAIM_LENGTH)
        profile = _string(raw["runner_profile"], f"{field}.runner_profile", max_length=64)
        if profile not in allowed_profiles:
            raise PolicyValidationError(
                f"{field}.runner_profile {profile!r} is not enabled by runner_profiles."
            )
        selector = validate_test_selector(_string(raw["selector"], f"{field}.selector"))
        if not RUNNER_PROFILES[profile].accepts_selector:
            raise PolicyValidationError(
                f"{field}.runner_profile {profile!r} does not accept per-test selectors."
            )
        rules.append(
            ObligationRule(
                obligation_id=obligation_id,
                category=category,
                severity=severity,
                claim=claim,
                runner_profile=profile,
                selector=selector,
            )
        )
    return tuple(rules)


def validate_policy_text(text: str) -> VerificationPolicy:
    """Parse and validate policy YAML; fail closed on malformed or unsafe input.

    The caller is responsible for obtaining this text from the trusted base commit,
    not from the pull-request head. Validation does not establish authenticity.
    """
    if not isinstance(text, str):
        raise PolicyValidationError("Policy input must be text.")
    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise PolicyValidationError("Policy input must be valid UTF-8 text.") from exc
    if len(encoded) > MAX_POLICY_BYTES:
        raise PolicyValidationError(f"Policy exceeds the {MAX_POLICY_BYTES}-byte limit.")
    if "\x00" in text:
        raise PolicyValidationError("Policy input must not contain NUL characters.")

    try:
        for token in yaml.scan(text):
            if isinstance(token, (AliasToken, AnchorToken)):
                raise PolicyValidationError("YAML anchors and aliases are not supported.")
        document: object = yaml.load(text, Loader=_UniqueKeySafeLoader)
    except yaml.YAMLError as exc:
        raise PolicyValidationError(f"Invalid policy YAML: {exc}") from exc

    raw = _mapping(document, "policy")
    _exact_keys(
        raw,
        field="policy",
        required={
            "version",
            "trusted_workflows",
            "runner_profiles",
            "severity_rules",
            "harness_sensitive_paths",
            "obligations",
        },
    )
    version = raw["version"]
    if type(version) is not int or version != 1:
        raise PolicyValidationError("version must be integer 1.")

    workflows = _string_list(
        raw["trusted_workflows"], "trusted_workflows", max_items=MAX_TRUSTED_WORKFLOWS
    )
    workflows = tuple(_validate_trusted_workflow(item) for item in workflows)

    profiles = _string_list(
        raw["runner_profiles"], "runner_profiles", max_items=MAX_RUNNER_PROFILES
    )
    for profile in profiles:
        if profile not in RUNNER_PROFILES:
            raise PolicyValidationError(f"Unknown fixed runner profile: {profile!r}.")

    sensitive_paths = _string_list(
        raw["harness_sensitive_paths"],
        "harness_sensitive_paths",
        max_items=MAX_HARNESS_PATHS,
        allow_trailing_slash=True,
    )
    sensitive_paths = tuple(_validate_sensitive_path(item) for item in sensitive_paths)
    missing_sensitive = _REQUIRED_HARNESS_PATHS - set(sensitive_paths)
    if missing_sensitive:
        raise PolicyValidationError(
            "harness_sensitive_paths omits mandatory protection(s): "
            + ", ".join(sorted(missing_sensitive))
            + "."
        )

    severity_rules = _parse_severity_rules(raw["severity_rules"])
    obligations = _parse_obligations(raw["obligations"], profiles)
    return VerificationPolicy(
        version=1,
        trusted_workflows=workflows,
        runner_profiles=profiles,
        severity_rules=severity_rules,
        harness_sensitive_paths=sensitive_paths,
        obligations=obligations,
    )


def command_for(
    policy: VerificationPolicy, profile_name: str, selector: str | None = None
) -> tuple[str, ...]:
    """Build an argv tuple from an enabled verifier-owned profile, never through a shell."""
    if profile_name not in policy.runner_profiles:
        raise PolicyValidationError(f"Runner profile {profile_name!r} is not enabled by policy.")
    profile = RUNNER_PROFILES[profile_name]
    if profile.accepts_selector:
        if selector is None:
            raise PolicyValidationError(f"Runner profile {profile_name!r} requires a selector.")
        return profile.argv_prefix + (validate_test_selector(selector),)
    if selector is not None:
        raise PolicyValidationError(f"Runner profile {profile_name!r} does not accept a selector.")
    return profile.argv_prefix
