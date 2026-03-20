"""FastMCP server for the Kling Omni Video API."""

from __future__ import annotations

import json
import os
import time
import typing as typ

import httpx
import jwt
from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

DEFAULT_BASE_URL = "https://api-singapore.klingai.com"
DEFAULT_TIMEOUT_SECONDS = 30.0

type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonObject]
type JsonData = JsonObject | JsonArray

type AspectRatio = typ.Literal["16:9", "9:16", "1:1"]
type DurationValue = typ.Literal[
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
]
type FrameType = typ.Literal["first_frame", "end_frame"]
type KeepOriginalSound = typ.Literal["yes", "no"]
type Mode = typ.Literal["std", "pro"]
type ModelName = typ.Literal["kling-video-o1", "kling-v3-omni"]
type ReferType = typ.Literal["feature", "base"]
type ShotType = typ.Literal["customize", "intelligence"]
type SoundMode = typ.Literal["on", "off"]


class KlingConfigurationError(RuntimeError):
    """Raised when the server is missing required configuration."""


class KlingApiError(RuntimeError):
    """Raised when the Kling API rejects a request or returns invalid data."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        service_code: int | None = None,
        request_id: str | None = None,
    ) -> None:
        """Build a descriptive API error."""
        details: list[str] = [message]
        if service_code is not None:
            details.append(f"service_code={service_code}")
        if http_status is not None:
            details.append(f"http_status={http_status}")
        if request_id:
            details.append(f"request_id={request_id}")
        super().__init__("; ".join(details))


class KlingSettings(BaseModel):
    """Configuration required to talk to the Kling API."""

    model_config = ConfigDict(extra="forbid")

    access_key: str = Field(min_length=1)
    secret_key: SecretStr
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> typ.Self:
        """Load settings from environment variables."""
        environ = os.environ if env is None else env
        access_key = environ.get("KLING_ACCESS_KEY", "").strip()
        secret_key = environ.get("KLING_SECRET_KEY", "").strip()
        if not access_key or not secret_key:
            msg = (
                "Missing Kling credentials. Set KLING_ACCESS_KEY and "
                "KLING_SECRET_KEY before using this server."
            )
            raise KlingConfigurationError(msg)

        base_url = environ.get("KLING_API_BASE_URL", DEFAULT_BASE_URL).strip()
        timeout_raw = environ.get("KLING_TIMEOUT_SECONDS")
        timeout_seconds = DEFAULT_TIMEOUT_SECONDS
        if timeout_raw:
            timeout_seconds = float(timeout_raw)

        return cls(
            access_key=access_key,
            secret_key=SecretStr(secret_key),
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )


class ImageReference(BaseModel):
    """An image used as a reference or boundary frame."""

    model_config = ConfigDict(extra="forbid")

    image_url: str = Field(min_length=1)
    type: FrameType | None = None


class ElementReference(BaseModel):
    """An element ID from the Kling element library."""

    model_config = ConfigDict(extra="forbid")

    element_id: int


class VideoReference(BaseModel):
    """A video used for reference or editing."""

    model_config = ConfigDict(extra="forbid")

    video_url: str = Field(min_length=1)
    refer_type: ReferType = "base"
    keep_original_sound: KeepOriginalSound | None = None


class StoryboardPrompt(BaseModel):
    """One shot definition in a multi-shot request."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1)
    prompt: str = Field(min_length=1, max_length=512)
    duration: DurationValue


class WatermarkInfo(BaseModel):
    """Whether Kling should also emit a watermarked output."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool


class CreateOmniVideoTaskRequest(BaseModel):
    """Validated request payload for `/v1/videos/omni-video`."""

    model_config = ConfigDict(extra="forbid")

    model_name: ModelName = "kling-video-o1"
    multi_shot: bool = False
    shot_type: ShotType | None = None
    prompt: str | None = Field(default=None, max_length=2500)
    multi_prompt: list[StoryboardPrompt] = Field(default_factory=list, max_length=6)
    image_list: list[ImageReference] = Field(default_factory=list)
    element_list: list[ElementReference] = Field(default_factory=list)
    video_list: list[VideoReference] = Field(default_factory=list)
    sound: SoundMode | None = None
    mode: Mode = "pro"
    aspect_ratio: AspectRatio | None = None
    duration: DurationValue | None = None
    watermark_info: WatermarkInfo | None = None
    callback_url: str | None = None
    external_task_id: str | None = None

    @model_validator(mode="after")
    def validate_request(self) -> typ.Self:
        """Enforce the documented cross-field API rules locally."""
        frame_types: set[FrameType] = {
            image.type for image in self.image_list if image.type is not None
        }
        has_first_frame = "first_frame" in frame_types
        has_end_frame = "end_frame" in frame_types
        has_reference_video = bool(self.video_list)
        has_base_video = any(video.refer_type == "base" for video in self.video_list)
        prompt = (self.prompt or "").strip()

        if self.multi_shot:
            self._validate_multi_shot(prompt, frame_types)
        else:
            self._validate_single_shot(prompt)

        if has_end_frame and not has_first_frame:
            msg = "An end_frame image requires a matching first_frame image."
            raise ValueError(msg)

        if has_reference_video and self.sound not in {None, "off"}:
            msg = "The sound parameter must be off when a reference video is present."
            raise ValueError(msg)

        if has_base_video:
            self._validate_base_video_rules(frame_types)
        elif not has_first_frame and self.aspect_ratio is None:
            msg = (
                "aspect_ratio is required unless the request uses a first-frame "
                "reference or base-video editing."
            )
            raise ValueError(msg)

        return self

    def _validate_multi_shot(
        self,
        prompt: str,
        frame_types: set[FrameType],
    ) -> None:
        """Validate the multi-shot configuration branches."""
        has_frame_boundaries = bool(frame_types)
        if self.shot_type is None:
            msg = "shot_type is required when multi_shot is true."
            raise ValueError(msg)
        if has_frame_boundaries:
            msg = "Multi-shot requests do not support first_frame or end_frame images."
            raise ValueError(msg)
        if self.shot_type == "customize":
            self._validate_custom_storyboards(prompt)
            return
        if not prompt:
            msg = "prompt is required for intelligence multi-shot requests."
            raise ValueError(msg)

    def _validate_custom_storyboards(self, prompt: str) -> None:
        """Validate the customize multi-shot mode."""
        if prompt:
            msg = "prompt must be empty when shot_type is customize."
            raise ValueError(msg)
        if not self.multi_prompt:
            msg = "multi_prompt is required when shot_type is customize."
            raise ValueError(msg)
        if self.duration is None:
            msg = "duration is required when validating storyboard durations."
            raise ValueError(msg)

        total_duration = sum(int(item.duration) for item in self.multi_prompt)
        if total_duration != int(self.duration):
            msg = "The sum of multi_prompt durations must equal the task duration."
            raise ValueError(msg)

    def _validate_single_shot(self, prompt: str) -> None:
        """Validate the single-shot branch."""
        if not prompt:
            msg = "prompt is required when multi_shot is false."
            raise ValueError(msg)
        if self.shot_type is not None:
            msg = "shot_type must be omitted when multi_shot is false."
            raise ValueError(msg)
        if self.multi_prompt:
            msg = "multi_prompt must be empty when multi_shot is false."
            raise ValueError(msg)

    def _validate_base_video_rules(self, frame_types: set[FrameType]) -> None:
        """Validate the base-video editing mode."""
        if frame_types:
            msg = "Base-video editing does not support first_frame or end_frame images."
            raise ValueError(msg)
        if self.aspect_ratio is not None:
            msg = "aspect_ratio is not supported when refer_type is base."
            raise ValueError(msg)
        if self.duration is not None:
            msg = "duration is not supported when refer_type is base."
            raise ValueError(msg)


class TaskLookup(BaseModel):
    """Lookup selector for a single async task."""

    model_config = ConfigDict(extra="forbid")

    task_id: str | None = None
    external_task_id: str | None = None

    @model_validator(mode="after")
    def validate_identifier(self) -> typ.Self:
        """Require exactly one identifier because the API uses one path slot."""
        provided = [value for value in (self.task_id, self.external_task_id) if value]
        if len(provided) != 1:
            msg = "Provide exactly one of task_id or external_task_id."
            raise ValueError(msg)
        return self

    def identifier(self) -> str:
        """Return the identifier that should be placed in the URL path."""
        return self.task_id or self.external_task_id or ""


class TaskListQuery(BaseModel):
    """Pagination parameters for list queries."""

    model_config = ConfigDict(extra="forbid")

    page_num: int = Field(default=1, ge=1, le=1000)
    page_size: int = Field(default=30, ge=1, le=500)


def build_bearer_token(
    *,
    access_key: str,
    secret_key: str,
    now: int | None = None,
) -> str:
    """Build the JWT token required by the Kling API."""
    issued_at = int(time.time()) if now is None else now
    payload = {
        "iss": access_key,
        "exp": issued_at + 1800,
        "nbf": issued_at - 5,
    }
    return jwt.encode(
        payload,
        secret_key,
        algorithm="HS256",
        headers={"typ": "JWT"},
    )


class KlingVideoApi:
    """HTTP client for the Kling Omni Video endpoints."""

    def __init__(
        self,
        settings: KlingSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Store API configuration and optional test transport."""
        self._settings = settings
        self._transport = transport

    async def create_omni_video_task(
        self,
        request: CreateOmniVideoTaskRequest,
    ) -> JsonData:
        """Submit a new async Kling video task."""
        return await self._request(
            "POST",
            "/v1/videos/omni-video",
            json_body=request.model_dump(exclude_none=True),
        )

    async def get_omni_video_task(self, lookup: TaskLookup) -> JsonData:
        """Fetch a single task by task ID or external task ID."""
        identifier = lookup.identifier()
        return await self._request("GET", f"/v1/videos/omni-video/{identifier}")

    async def list_omni_video_tasks(self, query: TaskListQuery) -> JsonData:
        """Fetch a paginated list of tasks."""
        params = {"pageNum": str(query.page_num), "pageSize": str(query.page_size)}
        return await self._request("GET", "/v1/videos/omni-video", params=params)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: JsonObject | None = None,
        params: dict[str, str] | None = None,
    ) -> JsonData:
        """Send a request and normalize the Kling API envelope."""
        headers = {"Authorization": self._build_authorization_header()}
        async with httpx.AsyncClient(
            base_url=self._settings.base_url,
            headers=headers,
            timeout=self._settings.timeout_seconds,
            transport=self._transport,
        ) as client:
            response = await client.request(
                method=method,
                url=path,
                json=json_body,
                params=params,
            )

        payload = self._parse_json_object(response)
        self._raise_for_api_error(response, payload)

        data = payload.get("data")
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return [self._ensure_json_object(item) for item in data]

        msg = "Kling API response did not include an object or list in data."
        raise KlingApiError(
            msg,
            http_status=response.status_code,
            request_id=self._request_id(payload),
        )

    def _build_authorization_header(self) -> str:
        """Build the full Authorization header value."""
        token = build_bearer_token(
            access_key=self._settings.access_key,
            secret_key=self._settings.secret_key.get_secret_value(),
        )
        return f"Bearer {token}"

    def _parse_json_object(self, response: httpx.Response) -> JsonObject:
        """Parse a response body and ensure it is a JSON object."""
        try:
            payload: object = response.json()
        except json.JSONDecodeError as exc:
            msg = "Kling API returned a non-JSON response."
            raise KlingApiError(msg, http_status=response.status_code) from exc
        return self._ensure_json_object(payload)

    def _raise_for_api_error(
        self,
        response: httpx.Response,
        payload: JsonObject,
    ) -> None:
        """Raise a structured error when either layer reports failure."""
        code = payload.get("code")
        if response.is_error or code != 0:
            message = payload.get("message")
            message_text = (
                message
                if isinstance(message, str) and message
                else "Kling API request failed."
            )
            raise KlingApiError(
                message_text,
                http_status=response.status_code,
                service_code=code if isinstance(code, int) else None,
                request_id=self._request_id(payload),
            )

    @staticmethod
    def _request_id(payload: JsonObject) -> str | None:
        """Extract the request ID when available."""
        request_id = payload.get("request_id")
        return request_id if isinstance(request_id, str) else None

    @staticmethod
    def _ensure_json_object(value: object) -> JsonObject:
        """Reject non-object values from the API payload."""
        if isinstance(value, dict):
            return typ.cast("JsonObject", value)
        msg = "Kling API returned invalid JSON data."
        raise KlingApiError(msg)


def create_server(
    *,
    settings_provider: typ.Callable[[], KlingSettings] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastMCP:
    """Create the FastMCP server instance."""
    resolve_settings = (
        KlingSettings.from_env if settings_provider is None else settings_provider
    )
    server = FastMCP("Kling Omni Video MCP Server")

    def make_api() -> KlingVideoApi:
        """Create a fresh API client for each request."""
        return KlingVideoApi(resolve_settings(), transport=transport)

    @server.tool(
        name="create_omni_video_task",
        description="Create an async Kling Omni Video generation task.",
    )
    async def create_omni_video_task(
        request: CreateOmniVideoTaskRequest,
    ) -> JsonData:
        """Submit a new Kling Omni Video task."""
        return await make_api().create_omni_video_task(request)

    @server.tool(
        name="get_omni_video_task",
        description="Fetch a Kling Omni Video task by task ID or external task ID.",
    )
    async def get_omni_video_task(lookup: TaskLookup) -> JsonData:
        """Fetch one Kling task."""
        return await make_api().get_omni_video_task(lookup)

    @server.tool(
        name="list_omni_video_tasks",
        description="List Kling Omni Video tasks with pagination.",
    )
    async def list_omni_video_tasks(query: TaskListQuery | None = None) -> JsonData:
        """List Kling tasks."""
        resolved_query = TaskListQuery() if query is None else query
        return await make_api().list_omni_video_tasks(resolved_query)

    return server


def main() -> None:
    """Run the FastMCP server over stdio."""
    create_server().run()
