# Kling Omni Video MCP Design

## Purpose

This project exposes Kling's Omni Video task API through a small FastMCP 2.0
server. The initial scope covers the three core async task operations:

- create a task
- fetch a single task
- list tasks

## Key decisions

### Environment-based credentials

Credentials are read from `KLING_ACCESS_KEY` and `KLING_SECRET_KEY`. This keeps
secrets out of tool arguments and matches how local MCP servers are typically
configured.

### Per-request JWT generation

Kling requires a short-lived JWT token in the `Authorization` header. The
server generates a new bearer token for every HTTP request so the caller does
not need to manage token expiry.

### Local validation before network calls

The server validates the most important documented cross-field rules before
sending a request. This prevents avoidable remote failures for common cases
such as:

- multi-shot requests missing `shot_type`
- `customize` storyboards whose durations do not sum to the task duration
- `end_frame` without `first_frame`
- invalid `sound`, `aspect_ratio`, or `duration` settings during base-video
  editing

### Thin endpoint mapping

The tools map directly to Kling endpoints:

- `create_omni_video_task` -> `POST /v1/videos/omni-video`
- `get_omni_video_task` -> `GET /v1/videos/omni-video/{identifier}`
- `list_omni_video_tasks` -> `GET /v1/videos/omni-video`

The implementation intentionally stays close to the upstream payload shape so
future endpoint additions can follow the same pattern without translation
layers.
