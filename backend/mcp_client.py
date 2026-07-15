"""Restricted MCP client for store operational data.

The database and MCP server live outside this project.  This module is only a
consumer and deliberately exposes a small allow-list of read-only tools.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator
from urllib.parse import urlparse


class MCPClientError(RuntimeError):
    """Raised when an MCP connection or tool call cannot be used safely."""


@dataclass(frozen=True)
class MCPToolInfo:
    """Minimal tool metadata needed by the data-acquisition agent."""

    name: str
    description: str
    input_schema: dict[str, Any]


class MCPToolSession:
    """Initialized MCP session with timeout, allow-list, and size guards."""

    def __init__(
        self,
        session: Any,
        *,
        allowed_tools: frozenset[str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> None:
        self._session = session
        self._allowed_tools = allowed_tools
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes

    async def list_tools(self) -> list[MCPToolInfo]:
        try:
            response = await asyncio.wait_for(
                self._session.list_tools(), timeout=self._timeout_seconds
            )
        except TimeoutError as exc:
            raise MCPClientError("MCP tool discovery timed out") from exc
        except Exception as exc:
            raise MCPClientError("MCP tool discovery failed") from exc

        tools: list[MCPToolInfo] = []
        for tool in response.tools:
            if tool.name not in self._allowed_tools:
                continue
            tools.append(
                MCPToolInfo(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=dict(tool.inputSchema or {}),
                )
            )
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self._allowed_tools:
            raise MCPClientError(f"MCP tool is not allowed: {name}")

        try:
            result = await asyncio.wait_for(
                self._session.call_tool(name, arguments=arguments),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise MCPClientError(f"MCP tool timed out: {name}") from exc
        except Exception as exc:
            raise MCPClientError(f"MCP tool call failed: {name}") from exc

        if result.isError:
            raise MCPClientError(f"MCP tool returned an error: {name}")

        payload = result.structuredContent
        if payload is None:
            payload = self._parse_text_payload(result.content)
        if not isinstance(payload, dict):
            raise MCPClientError(f"MCP tool returned invalid structured data: {name}")

        encoded = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        if len(encoded) > self._max_response_bytes:
            raise MCPClientError(f"MCP tool response is too large: {name}")
        return payload

    @staticmethod
    def _parse_text_payload(content: list[Any]) -> dict[str, Any] | None:
        texts = [item.text for item in content if getattr(item, "type", None) == "text"]
        if not texts:
            return None
        try:
            parsed = json.loads("\n".join(texts))
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None


class MCPToolClient:
    """Creates short-lived Streamable HTTP MCP sessions."""

    def __init__(
        self,
        server_url: str,
        *,
        allowed_tools: set[str] | frozenset[str],
        timeout_seconds: float = 10.0,
        max_response_bytes: int = 1_000_000,
        auth_token: str = "",
    ) -> None:
        parsed_url = urlparse(server_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            raise ValueError("MCP_SERVER_URL must be an absolute HTTP(S) URL")
        if parsed_url.username or parsed_url.password:
            raise ValueError("MCP_SERVER_URL must not contain embedded credentials")
        loopback_hosts = {"localhost", "127.0.0.1", "::1"}
        if parsed_url.scheme == "http" and parsed_url.hostname not in loopback_hosts:
            raise ValueError("Remote MCP servers must use HTTPS")
        self.server_url = server_url
        self.allowed_tools = frozenset(allowed_tools)
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.auth_token = auth_token

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[MCPToolSession]:
        try:
            import httpx
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
        except ImportError as exc:
            raise MCPClientError(
                "MCP support is enabled but the mcp/httpx dependencies are unavailable"
            ) from exc

        timeout = httpx.Timeout(
            self.timeout_seconds,
            connect=self.timeout_seconds,
            read=self.timeout_seconds,
            write=self.timeout_seconds,
            pool=self.timeout_seconds,
        )
        try:
            headers = (
                {"Authorization": f"Bearer {self.auth_token}"}
                if self.auth_token
                else None
            )
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                trust_env=False,
                headers=headers,
            ) as http_client:
                async with streamable_http_client(
                    self.server_url,
                    http_client=http_client,
                    terminate_on_close=True,
                ) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await asyncio.wait_for(
                            session.initialize(), timeout=self.timeout_seconds
                        )
                        yield MCPToolSession(
                            session,
                            allowed_tools=self.allowed_tools,
                            timeout_seconds=self.timeout_seconds,
                            max_response_bytes=self.max_response_bytes,
                        )
        except MCPClientError:
            raise
        except TimeoutError as exc:
            raise MCPClientError("MCP connection timed out") from exc
        except Exception as exc:
            raise MCPClientError("MCP connection failed") from exc
