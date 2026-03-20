# Users' Guide

## Overview

`klingy-mcp` wraps Kling's Omni Video API as a local MCP server. It is intended
for clients that want to submit async video jobs, poll their status, and list
recent tasks without reimplementing Kling's JWT authentication flow.

## Installation

Install the server from the repository root:

```bash
uv tool install .
```

The installed command is `klingy-mcp`.

## Required configuration

Set the following environment variables before launching the server:

- `KLING_ACCESS_KEY`
- `KLING_SECRET_KEY`

Optional variables:

- `KLING_API_BASE_URL`
  Defaults to `https://api-singapore.klingai.com`.
- `KLING_TIMEOUT_SECONDS`
  Defaults to `30`.

## Running the server

Start the FastMCP server over stdio:

```bash
klingy-mcp
```

## Tool reference

### `create_omni_video_task`

Creates a task through `POST /v1/videos/omni-video`.

The tool accepts a single `request` object with Kling's request fields,
including:

- `model_name`
- `multi_shot`
- `shot_type`
- `prompt`
- `multi_prompt`
- `image_list`
- `element_list`
- `video_list`
- `sound`
- `mode`
- `aspect_ratio`
- `duration`
- `watermark_info`
- `callback_url`
- `external_task_id`

Local validation rejects invalid combinations before the request reaches Kling.
Examples:

- `end_frame` without `first_frame`
- `sound="on"` while `video_list` is present
- `aspect_ratio` or `duration` supplied for `refer_type="base"`
- missing `shot_type` or `multi_prompt` in multi-shot mode

### `get_omni_video_task`

Fetches a single task by providing exactly one identifier inside the `lookup`
object:

- `task_id`
- `external_task_id`

### `list_omni_video_tasks`

Lists tasks with an optional `query` object:

- `page_num`
- `page_size`

If omitted, the tool uses Kling's documented defaults of page `1` and page size
`30`.

## Behaviour notes

- The server generates a fresh JWT bearer token for every request.
- Kling API errors are surfaced with the service code, HTTP status, and request
  ID when available.
- Callback payloads are passed through unchanged by Kling. This server does not
  host a callback endpoint; it simply forwards `callback_url` during task
  creation.
