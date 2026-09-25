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
on a push, so the ratchet catches up at the next push to `main`. No `env` binds
`CS_ACCESS_TOKEN`: a check step writes whether the secret is set, from an
expression evaluated before its shell runs, and the upload step receives the
token only as its `access-token` input, because the uploader is a composite
action that would pass its step's `env` to its nested steps. The upload runs
only when the token is present and the ref is `refs/heads/main`, so a dispatch
from a branch cannot publish that branch's coverage as the trunk's. Merges made
by the Dependabot automerge workflow use `GITHUB_TOKEN` and fire no push event,
so they are measured only at the next push to `main` or a manual dispatch; this
is a known exception, tracked in leynos/shared-actions#518. The publisher's
concurrency group is keyed on the ref alone and never cancels a run in progress,
so runs on `main` never overlap and a newer triggered run (push or dispatch)
replaces any pending one. A manual re-run of an older run is an operator action
that republishes that commit's coverage and baseline until the next push
supersedes it; a dispatch that replaces a pending push leaves the ratchet
baseline one commit behind until the next push, also tracked in
leynos/shared-actions#518. No other workflow a push starts, directly or through
a local call, may generate coverage outside the pull-request guard, and that
includes a workflow the publisher itself calls, so the publisher's own coverage
step is the only baseline writer. Both coverage steps select the same
inputs at the same `shared-actions` pin because the pull-request ratchet is only
meaningful against a baseline measured the same way.

`tests/workflow_contracts/test_codescene_pull_request_contract.py`,
`tests/workflow_contracts/test_codescene_publisher_contract.py` and
`tests/workflow_contracts/test_codescene_token_contract.py` hold this shape,
with the rules in `tests/workflow_contracts/codescene_pull_request_rules.py`,
`tests/workflow_contracts/codescene_publisher_rules.py`,
`tests/workflow_contracts/codescene_token_rules.py` and
`tests/workflow_contracts/codescene_coverage_rules.py`, and the strict workflow
reader in `tests/workflow_contracts/codescene_workflow_reader.py`, which
`tests/workflow_contracts/codescene_workflow_files.py` feeds from disk. The
rules read every workflow a pull request can start, from its own events,
reviews and comments, a merge queue, or a push not confined to `main` or tags,
following local reusable-workflow calls, `workflow_run` chains and local
composite actions, and refuse any mention of the CodeScene host, uploader,
client, or token there. They also refuse `continue-on-error` wherever it would
turn a failed ratchet or upload green.
Each clause has a test that mutates the workflows and expects the clause to
refuse the result.
