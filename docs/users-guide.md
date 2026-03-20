# Users' guide

## Overview

`klingy-mcp` exposes Kling's Omni Video API as a local Model Context Protocol
(MCP) server. It is intended for MCP clients that need to:

- create async video-generation tasks,
- poll task state and final outputs, and
- list recent tasks without reimplementing Kling's authentication flow.

The server currently wraps Kling's Omni Video task endpoints under
`https://api-singapore.klingai.com` and generates a fresh JSON Web Token (JWT)
bearer token for every outbound API request.

## Intended audience

This guide is written for developers and operators who want to install the
server locally, connect it to an MCP client, and use it as a thin wrapper
around Kling's async video workflow.

## What the server does

The server provides three MCP tools:

- `create_omni_video_task`
  Creates a new Omni Video task.
- `get_omni_video_task`
  Fetches a single task by Kling task ID or external task ID.
- `list_omni_video_tasks`
  Lists recent tasks with pagination.

The server keeps Kling's request and response shapes close to the upstream API.
That is deliberate. It keeps the MCP layer predictable and makes it easier to
track Kling's own documentation.

## What the server does not do

The current implementation does not:

- download generated videos,
- host a callback endpoint,
- persist task state locally,
- retry failed requests automatically, or
- expose image generation or other Kling endpoints.

## Installation

### Install as a tool

Install from the repository root:

```bash
uv tool install .
```

This installs the `klingy-mcp` console command defined in `pyproject.toml`.

### Install into an existing environment

If the server should live inside an existing Python environment:

```bash
uv pip install .
```

### Verify the installation

Confirm that the console entrypoint is available:

```bash
klingy-mcp --help
```

If the MCP host invokes the process directly, `python -m klingy_mcp` is also
supported.

## Configuration

### Required environment variables

Set both variables before launching the server:

- `KLING_ACCESS_KEY`
- `KLING_SECRET_KEY`

If either variable is missing, tool calls fail with a configuration error
before any request is sent to Kling.

Example shell configuration:

```bash
export KLING_ACCESS_KEY="your-access-key"
export KLING_SECRET_KEY="your-secret-key"
```

### Optional environment variables

- `KLING_API_BASE_URL`
  Defaults to `https://api-singapore.klingai.com`.
- `KLING_TIMEOUT_SECONDS`
  Defaults to `30`.

Example:

```bash
export KLING_API_BASE_URL="https://api-singapore.klingai.com"
export KLING_TIMEOUT_SECONDS="45"
```

### Authentication behaviour

The server does not accept a bearer token from the MCP client. Instead it:

1. reads the access key and secret key from the environment,
2. builds a short-lived JWT with `iss`, `exp`, and `nbf` claims, and
3. sends `Authorization: Bearer <token>` on every HTTP request.

This means the MCP client never needs to manage Kling token expiry directly.

## Running the server

Start the server over standard input and output:

```bash
klingy-mcp
```

This is the normal transport for local MCP hosts.

## Connecting an MCP client

The exact configuration depends on the MCP host, but the important detail is
that the host should launch `klingy-mcp` as a stdio server with the required
environment variables present.

A representative configuration shape looks like this:

```json
{
  "command": "klingy-mcp",
  "env": {
    "KLING_ACCESS_KEY": "your-access-key",
    "KLING_SECRET_KEY": "your-secret-key"
  }
}
```

## Tool reference

## `create_omni_video_task`

Creates a task by calling `POST /v1/videos/omni-video`.

### Create input shape

The tool expects a single top-level argument named `request`. The value is an
object that mirrors Kling's request body.

Common fields:

- `model_name`
  Either `kling-video-o1` or `kling-v3-omni`. Defaults to `kling-video-o1`.
- `multi_shot`
  Boolean. Defaults to `false`.
- `shot_type`
  Used only for multi-shot requests. Either `customize` or `intelligence`.
- `prompt`
  Main prompt text. Maximum length is 2,500 characters.
- `multi_prompt`
  Storyboard array for custom multi-shot requests.
- `image_list`
  Reference images or first-frame/end-frame images.
- `element_list`
  Element IDs from Kling's element library.
- `video_list`
  Reference or base-editing video input.
- `sound`
  `on` or `off`.
- `mode`
  `std` or `pro`. Defaults to `pro`.
- `aspect_ratio`
  `16:9`, `9:16`, or `1:1`.
- `duration`
  A string value from `3` to `15`.
- `watermark_info`
  Object with `enabled: true|false`.
- `callback_url`
  Optional callback endpoint forwarded to Kling.
- `external_task_id`
  Optional caller-defined unique task identifier.

### Example: text-to-video

```json
{
  "request": {
    "prompt": "A woman walking through a neon-lit street at night.",
    "mode": "pro",
    "aspect_ratio": "16:9",
    "duration": "5"
  }
}
```

### Example: image reference

```json
{
  "request": {
    "prompt": "Make the person in <<<image_1>>> wave to the camera.",
    "image_list": [
      {
        "image_url": "https://example.com/reference.png"
      }
    ],
    "mode": "pro",
    "aspect_ratio": "16:9",
    "duration": "5"
  }
}
```

### Example: start and end frame

```json
{
  "request": {
    "prompt": "The subject turns and smiles.",
    "image_list": [
      {
        "image_url": "https://example.com/start.png",
        "type": "first_frame"
      },
      {
        "image_url": "https://example.com/end.png",
        "type": "end_frame"
      }
    ],
    "mode": "pro",
    "duration": "5"
  }
}
```

### Example: base-video editing

```json
{
  "request": {
    "prompt": "Replace the hat with a silver crown.",
    "video_list": [
      {
        "video_url": "https://example.com/source.mp4",
        "refer_type": "base",
        "keep_original_sound": "yes"
      }
    ],
    "mode": "pro"
  }
}
```

### Example: custom multi-shot request

```json
{
  "request": {
    "model_name": "kling-v3-omni",
    "multi_shot": true,
    "shot_type": "customize",
    "prompt": "",
    "multi_prompt": [
      {
        "index": 1,
        "prompt": "Two friends sit in a quiet cafe at dawn.",
        "duration": "2"
      },
      {
        "index": 2,
        "prompt": "The camera moves closer as they exchange a smile.",
        "duration": "3"
      }
    ],
    "mode": "pro",
    "aspect_ratio": "16:9",
    "duration": "5"
  }
}
```

### Local validation rules

The server performs local validation before making the HTTP request. This does
not replace Kling's own validation, but it catches the most important
cross-field failures early.

The current checks include:

- `prompt` is required when `multi_shot` is `false`.
- `shot_type` must be omitted when `multi_shot` is `false`.
- `multi_prompt` must be empty when `multi_shot` is `false`.
- `shot_type` is required when `multi_shot` is `true`.
- `first_frame` and `end_frame` images are rejected for multi-shot requests.
- `shot_type="customize"` requires `multi_prompt`.
- `shot_type="customize"` also requires the sum of storyboard durations to
  equal the top-level `duration`.
- `shot_type="customize"` requires an empty top-level `prompt`.
- `shot_type="intelligence"` requires a non-empty `prompt`.
- `end_frame` is rejected unless a matching `first_frame` is also present.
- `sound="on"` is rejected when any `video_list` input is present.
- `refer_type="base"` rejects `aspect_ratio`.
- `refer_type="base"` rejects `duration`.
- `refer_type="base"` rejects first-frame and end-frame image usage.
- `aspect_ratio` is required unless the request uses a first-frame image or
  base-video editing.

### Create response shape

On success, the tool returns Kling's `data` object rather than the whole
envelope. Typical fields include:

- `task_id`
- `task_status`
- `task_info`
- `created_at`
- `updated_at`

## `get_omni_video_task`

Fetches a single task by calling `GET /v1/videos/omni-video/{identifier}`.

### Input shape

The tool expects a top-level `lookup` object. Provide exactly one of:

- `task_id`
- `external_task_id`

If both are present, or both are omitted, the server rejects the request before
contacting Kling.

### Lookup example

```json
{
  "lookup": {
    "task_id": "task-123"
  }
}
```

### Lookup response shape

On success, the tool returns Kling's task `data` object. Depending on task
state, that can include:

- `task_id`
- `task_status`
- `task_status_msg`
- `task_info`
- `task_result`
- `watermark_info`
- `final_unit_deduction`
- `created_at`
- `updated_at`

Completed video tasks typically expose `task_result.videos`, including the
generated video ID, URL, optional watermarked URL, and duration.

## `list_omni_video_tasks`

Lists tasks by calling `GET /v1/videos/omni-video`.

### List input shape

The tool accepts an optional `query` object with:

- `page_num`
  Integer from `1` to `1000`. Defaults to `1`.
- `page_size`
  Integer from `1` to `500`. Defaults to `30`.

### List example

```json
{
  "query": {
    "page_num": 1,
    "page_size": 50
  }
}
```

If the `query` object is omitted, the server sends Kling's documented defaults.

### List response shape

The tool returns the `data` array from Kling's response. Each item is a task
summary with the same general fields returned by `get_omni_video_task`.

## Kling request behaviour

### Timeouts

The server uses an `httpx` timeout configured by `KLING_TIMEOUT_SECONDS`. The
default is `30` seconds.

### Error propagation

If Kling returns a non-zero service code or an HTTP error status, the server
raises an error that includes:

- Kling's `message` when available,
- the service code when available,
- the HTTP status code, and
- the request ID when Kling returns one.

This makes it easier to correlate client-visible failures with Kling support
requests.

### Callback behaviour

If `callback_url` is supplied on task creation, the server forwards it to Kling
unchanged. The server itself does not receive or store callbacks.

## Working patterns

### Recommended flow

For most clients, the stable workflow is:

1. call `create_omni_video_task`,
2. record the returned `task_id`,
3. poll with `get_omni_video_task` until `task_status` becomes `succeed` or
   `failed`, and
4. consume the returned video URLs promptly, because Kling documents generated
   assets as temporary.

### Using `external_task_id`

Use `external_task_id` when the caller already has its own durable task or job
identifier. This makes it easier to join Kling tasks back to internal records.

## Troubleshooting

### Missing credentials

Symptom:

```plaintext
Missing Kling credentials. Set KLING_ACCESS_KEY and KLING_SECRET_KEY before using this server.
```

Cause:

- the required environment variables are not set in the MCP host process.

Resolution:

- set both variables in the shell or MCP host configuration, then restart the
  server process.

### Authentication failures from Kling

Likely causes:

- incorrect access key,
- incorrect secret key,
- expired or not-yet-valid JWT according to Kling, or
- requests being sent to the wrong Kling API domain.

Resolution:

- verify `KLING_ACCESS_KEY`,
- verify `KLING_SECRET_KEY`,
- verify `KLING_API_BASE_URL`, and
- retry after confirming system time is reasonable.

### Validation errors before network calls

Symptom:

- the MCP tool fails immediately without a Kling request being sent.

Cause:

- the request violates one of the server's local cross-field validation rules.

Resolution:

- compare the payload against the validation list in this guide,
- check multi-shot combinations carefully, and
- check first-frame/end-frame and base-video editing constraints.

### Kling request rejected after local validation passes

Cause:

- Kling applies additional upstream rules that the local server does not model
  yet, such as asset accessibility, file size, or unsupported model-feature
  combinations.

Resolution:

- inspect Kling's returned `message`, service code, and request ID,
- confirm that referenced images and videos are accessible to Kling, and
- reduce the payload to the smallest failing example before widening scope
  again.

## Upgrade and maintenance notes

- Reinstall the package after pulling new code if it was installed with
  `uv tool install .`.
- Review [README.md](../README.md) for the short operational summary.
- Review
  [docs/kling-omni-video-mcp-design.md](kling-omni-video-mcp-design.md) for the
  design-level rationale behind the server shape and validation strategy.
