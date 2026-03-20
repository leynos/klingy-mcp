from __future__ import annotations

import json

import httpx
import jwt
import pytest
from fastmcp import Client
from mcp.types import CallToolResult, TextContent
from pydantic import SecretStr, ValidationError

from klingy_mcp.server import (
    CreateOmniVideoTaskRequest,
    ImageReference,
    KlingSettings,
    TaskLookup,
    build_bearer_token,
    create_server,
)


def _result_json(result: CallToolResult) -> object:
    content = result.content[0]
    assert isinstance(content, TextContent)
    text = content.text
    return json.loads(text)


def test_build_bearer_token_uses_expected_claims() -> None:
    issued_at = 1_710_000_000

    token = build_bearer_token(
        access_key="demo-ak",
        secret_key="demo-secret-key-with-at-least-32-bytes",
        now=issued_at,
    )

    payload = jwt.decode(
        token,
        "demo-secret-key-with-at-least-32-bytes",
        algorithms=["HS256"],
        options={
            "verify_exp": False,
            "verify_nbf": False,
            "verify_iat": False,
        },
    )
    header = jwt.get_unverified_header(token)

    assert header == {"alg": "HS256", "typ": "JWT"}
    assert payload == {
        "iss": "demo-ak",
        "exp": issued_at + 1800,
        "nbf": issued_at - 5,
    }


def test_create_request_rejects_end_frame_without_first_frame() -> None:
    with pytest.raises(ValidationError, match="first_frame"):
        CreateOmniVideoTaskRequest(
            prompt="Animate the subject",
            image_list=[
                ImageReference(
                    image_url="https://example.com/end-frame.png",
                    type="end_frame",
                )
            ],
            mode="pro",
        )


def test_task_lookup_requires_exactly_one_identifier() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        TaskLookup(task_id="task-1", external_task_id="external-1")


@pytest.mark.asyncio
async def test_create_task_tool_invokes_kling_api() -> None:
    expected_response = {
        "code": 0,
        "message": "ok",
        "request_id": "req-123",
        "data": {
            "task_id": "task-123",
            "task_status": "submitted",
            "task_info": {"external_task_id": "external-123"},
            "created_at": 1722769557708,
            "updated_at": 1722769557708,
        },
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        json_body = json.loads(request.content.decode())

        assert request.method == "POST"
        assert (
            str(request.url) == "https://api-singapore.klingai.com/v1/videos/omni-video"
        )
        assert request.headers["content-type"] == "application/json"
        assert request.headers["authorization"].startswith("Bearer ")
        assert json_body["prompt"] == "Make the subject wave"
        return httpx.Response(200, json=expected_response)

    server = create_server(
        settings_provider=lambda: KlingSettings(
            access_key="demo-ak",
            secret_key=SecretStr("demo-secret-key-with-at-least-32-bytes"),
        ),
        transport=httpx.MockTransport(handler),
    )

    async with Client(server) as client:
        result = await client.call_tool(
            "create_omni_video_task",
            {
                "request": {
                    "prompt": "Make the subject wave",
                    "image_list": [{"image_url": "https://example.com/reference.png"}],
                    "mode": "pro",
                    "aspect_ratio": "16:9",
                    "duration": "5",
                }
            },
        )

    assert _result_json(result) == expected_response["data"]


@pytest.mark.asyncio
async def test_get_task_tool_supports_external_task_id_lookup() -> None:
    expected_response = {
        "code": 0,
        "message": "ok",
        "request_id": "req-456",
        "data": {
            "task_id": "task-456",
            "task_status": "succeed",
            "task_status_msg": "",
            "task_info": {"external_task_id": "external-456"},
            "task_result": {
                "videos": [
                    {
                        "id": "video-1",
                        "url": "https://example.com/video.mp4",
                        "duration": "5",
                    }
                ]
            },
            "created_at": 1722769557708,
            "updated_at": 1722769557708,
        },
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert (
            str(request.url)
            == "https://api-singapore.klingai.com/v1/videos/omni-video/external-456"
        )
        return httpx.Response(200, json=expected_response)

    server = create_server(
        settings_provider=lambda: KlingSettings(
            access_key="demo-ak",
            secret_key=SecretStr("demo-secret-key-with-at-least-32-bytes"),
        ),
        transport=httpx.MockTransport(handler),
    )

    async with Client(server) as client:
        result = await client.call_tool(
            "get_omni_video_task",
            {"lookup": {"external_task_id": "external-456"}},
        )

    assert _result_json(result) == expected_response["data"]


@pytest.mark.asyncio
async def test_list_tasks_tool_uses_pagination_defaults() -> None:
    expected_response = {
        "code": 0,
        "message": "ok",
        "request_id": "req-789",
        "data": [
            {
                "task_id": "task-789",
                "task_status": "processing",
                "task_status_msg": "",
                "task_info": {"external_task_id": "external-789"},
                "created_at": 1722769557708,
                "updated_at": 1722769557708,
            }
        ],
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == (
            "https://api-singapore.klingai.com/v1/videos/omni-video"
            "?pageNum=1&pageSize=30"
        )
        return httpx.Response(200, json=expected_response)

    server = create_server(
        settings_provider=lambda: KlingSettings(
            access_key="demo-ak",
            secret_key=SecretStr("demo-secret-key-with-at-least-32-bytes"),
        ),
        transport=httpx.MockTransport(handler),
    )

    async with Client(server) as client:
        result = await client.call_tool("list_omni_video_tasks", {})

    assert _result_json(result) == expected_response["data"]
