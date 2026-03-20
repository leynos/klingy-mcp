# klingy-mcp

`klingy-mcp` is an installable FastMCP server for the Kling Omni Video API. It
exposes the async video task workflow over MCP and handles Kling's JWT
authentication scheme automatically.

## Install

Install the package from this repository:

```bash
uv tool install .
```

Or install it into an existing environment:

```bash
uv pip install .
```

Both paths expose the `klingy-mcp` script entrypoint defined in
`pyproject.toml`.

## Configure

Set the Kling credentials before starting the server:

```bash
export KLING_ACCESS_KEY="your-access-key"
export KLING_SECRET_KEY="your-secret-key"
```

Optional environment variables:

- `KLING_API_BASE_URL`
  Defaults to `https://api-singapore.klingai.com`.
- `KLING_TIMEOUT_SECONDS`
  Defaults to `30`.

## Run

Run the server over stdio:

```bash
klingy-mcp
```

You can also start it as a Python module:

```bash
python -m klingy_mcp
```

## Tools

The server exposes three tools:

- `create_omni_video_task`
  Creates a task for `POST /v1/videos/omni-video`.
- `get_omni_video_task`
  Fetches one task by `task_id` or `external_task_id`.
- `list_omni_video_tasks`
  Lists tasks with `page_num` and `page_size` pagination.

The tool payloads mirror Kling's request bodies closely, while adding local
validation for the most important cross-field rules such as multi-shot
requirements, first-frame/end-frame constraints, and base-video editing
restrictions.

More detailed usage notes live in [the users' guide](docs/users-guide.md).
