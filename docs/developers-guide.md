# klingy-mcp Developers' Guide

## Coverage workflow

Pull-request continuous integration (CI) generates Python coverage and ratchets
it against the baseline written by `coverage-main.yml`. The pull-request lane
publishes no coverage artefact, never contacts CodeScene, and never receives
`CS_ACCESS_TOKEN`, so a change in CodeScene's application programming interface
(API) cannot hold a pull request.

`coverage-main.yml` is the only publisher. On each push to `main` it refreshes
the ratchet baseline and uploads the report to CodeScene. It also runs on demand
through `workflow_dispatch`, for merges that fire no push event: a dispatch on
`main` uploads a fresh report, but the shared action advances the baseline only
on a push, so the ratchet catches up at the next push to `main`. The upload step
binds the token itself and runs only when the token is present and the ref is
`refs/heads/main`, so a dispatch from a branch cannot publish that branch's
coverage as the trunk's. Its concurrency group is keyed on the ref and the event
and never cancels a run in progress; a newer push replaces any pending run, so
the newest baseline wins. No other workflow a push starts, directly or through a
local call, may generate coverage outside the pull-request guard, so the
publisher is the only baseline writer. Both coverage steps select the same
inputs at the same `shared-actions` pin because the pull-request ratchet is only
meaningful against a baseline measured the same way.

The contract tests in `tests/workflow_contracts/` hold this shape:
`test_codescene_pull_request_contract.py` and
`test_codescene_publisher_contract.py`, with the rules in
`codescene_pull_request_rules.py`, `codescene_publisher_rules.py` and
`codescene_coverage_rules.py`, and the strict workflow reader in
`codescene_workflow_reader.py`. The rules read every workflow a pull request can
start, from its own events, reviews and comments, a merge queue, or a push not
confined to `main` or tags, following local reusable-workflow calls and
`workflow_run` chains, and refuse any mention of the CodeScene host, uploader,
client, or token there. They also refuse `continue-on-error` wherever it would
turn a failed ratchet or upload green. Each clause has a test that mutates the
workflows and expects the clause to refuse the result.
