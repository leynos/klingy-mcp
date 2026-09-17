"""Contract tests for main-owned CodeScene coverage publication.

Pull requests use the shared action's local coverage ratchet.  The main-only
workflow publishes the resulting report to CodeScene, keeping the external
coverage service out of pull-request execution.
"""

from __future__ import annotations

import re
import typing as typ
from pathlib import Path

import yaml

WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / ".github" / "workflows"
SHARED_ACTION_REVISION = "152d9c4784d0ae5877938a984fe6d1f04d718fd8"
CODE_SCENE_TEXT = re.compile(r"(?:CodeScene|cs-coverage)", re.IGNORECASE)


def _mapping(value: object, message: str) -> dict[typ.Any, typ.Any]:
    """Assert that a decoded YAML value is a mapping and narrow its type."""
    assert isinstance(value, dict), message
    return typ.cast("dict[typ.Any, typ.Any]", value)


def _load_workflow(name: str) -> dict[typ.Any, typ.Any]:
    """Load one workflow from the repository's workflow directory."""
    path = WORKFLOWS_DIR / name
    return _mapping(
        yaml.safe_load(path.read_text(encoding="utf-8")),
        f"{path} must parse to a YAML mapping",
    )


def _trigger(workflow: dict[typ.Any, typ.Any]) -> object:
    """Return a workflow trigger while accounting for YAML 1.1 parsing."""
    return workflow.get("on", workflow.get(True))


def _job(workflow: dict[typ.Any, typ.Any], name: str) -> dict[typ.Any, typ.Any]:
    """Return a named workflow job as a typed mapping."""
    jobs = _mapping(workflow.get("jobs"), "workflow must declare jobs")
    return _mapping(jobs.get(name), f"workflow must declare {name}")


def _steps(job: dict[typ.Any, typ.Any]) -> list[dict[typ.Any, typ.Any]]:
    """Return mapping-valued steps from a workflow job."""
    raw_steps = job.get("steps")
    assert isinstance(raw_steps, list), "workflow job must declare steps"
    return [_mapping(step, "workflow steps must be mappings") for step in raw_steps]


def _uses(step: dict[typ.Any, typ.Any], action: str) -> bool:
    """Return whether a workflow step uses the named action."""
    value = step.get("uses")
    return isinstance(value, str) and action in value


def _coverage_step(job: dict[typ.Any, typ.Any]) -> dict[typ.Any, typ.Any]:
    """Return the job's shared coverage-generation step."""
    coverage_steps = [step for step in _steps(job) if _uses(step, "generate-coverage")]
    assert len(coverage_steps) == 1, "workflow must have one coverage step"
    return coverage_steps[0]


def _assert_shared_coverage_inputs(
    step: dict[typ.Any, typ.Any],
) -> None:
    """Assert the shared action revision, source scope, and local ratchet."""
    uses = step.get("uses")
    assert uses == (
        "leynos/shared-actions/.github/actions/generate-coverage@"
        f"{SHARED_ACTION_REVISION}"
    )
    inputs = _mapping(step.get("with"), "coverage step must declare inputs")
    assert inputs.get("output-path") == "coverage.xml"
    assert inputs.get("format") == "cobertura"
    assert inputs.get("python-source") == "./klingy_mcp"
    assert inputs.get("pytest-workers") == ""
    assert inputs.get("with-ratchet") == "true"


def test_pull_requests_run_only_local_ratcheted_coverage() -> None:
    """Keep PR coverage independent of CodeScene and full-history checkout."""
    workflow = _load_workflow("ci.yml")
    trigger = _mapping(_trigger(workflow), "CI must declare event triggers")
    assert "pull_request" in trigger

    lint_test = _job(workflow, "lint-test")
    coverage_step = _coverage_step(lint_test)
    assert coverage_step.get("if") == "github.event_name == 'pull_request'"
    _assert_shared_coverage_inputs(coverage_step)

    assert "CS_ACCESS_TOKEN" not in workflow
    assert not any(
        _uses(step, "upload-codescene-coverage")
        or (isinstance(step.get("run"), str) and CODE_SCENE_TEXT.search(step["run"]))
        for step in _steps(lint_test)
    )
    for step in _steps(lint_test):
        if not _uses(step, "actions/checkout"):
            continue
        inputs = step.get("with", {})
        assert not isinstance(inputs, dict) or inputs.get("fetch-depth") not in {
            0,
            "0",
        }


def test_main_publishes_ratcheted_coverage() -> None:
    """Run and publish the ratcheted report only from main."""
    workflow = _load_workflow("coverage-main.yml")
    trigger = _mapping(_trigger(workflow), "coverage workflow must declare triggers")
    assert set(trigger) == {"push", "workflow_dispatch"}
    assert _mapping(trigger["push"], "push trigger must be a mapping").get(
        "branches"
    ) == ["main"]

    coverage_upload = _job(workflow, "coverage-upload")
    _assert_shared_coverage_inputs(_coverage_step(coverage_upload))
    upload_steps = [
        step
        for step in _steps(coverage_upload)
        if _uses(step, "upload-codescene-coverage")
    ]
    assert len(upload_steps) == 1, "main workflow must have one CodeScene upload"
    upload = upload_steps[0]
    assert upload.get("uses") == (
        "leynos/shared-actions/.github/actions/upload-codescene-coverage@"
        f"{SHARED_ACTION_REVISION}"
    )
    upload_inputs = _mapping(upload.get("with"), "upload must declare inputs")
    assert upload_inputs.get("mode") == "upload"
    assert upload_inputs.get("path") == "coverage.xml"
    assert upload_inputs.get("access-token") == "${{ env.CS_ACCESS_TOKEN }}"
