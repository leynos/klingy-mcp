# klingy-mcp Developers' Guide

## Coverage workflow

Pull-request jobs generate coverage with the shared coverage action and compare
it against the ratchet baseline written by the `main` coverage workflow.  They
run serially so that pull requests and `main` measure the same test suite.  A
pull-request job does not invoke CodeScene, carry its project URL, or expose
`CS_ACCESS_TOKEN`.

The `coverage-main.yml` workflow runs on `main` pushes and can be dispatched
manually when a merge mechanism does not emit a push event.  It uses the same
coverage inputs, advances the ratchet baseline, and publishes the report to
CodeScene with upload mode.  The CodeScene token and CLI checksum are scoped to
that main-only publishing job.
