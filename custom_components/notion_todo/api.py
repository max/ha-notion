"""Notion API client for Notion Todo."""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import aiohttp

from .const import NOTION_VERSION

NOTION_API_BASE = "https://api.notion.com/v1"


class NotionTodoApiClientError(Exception):
    """Exception to indicate a general API error."""


class NotionTodoApiClientCommunicationError(NotionTodoApiClientError):
    """Exception to indicate a communication error."""


class NotionTodoApiClientAuthenticationError(NotionTodoApiClientError):
    """Exception to indicate an authentication error."""


class NotionTodoApiClientNotFoundError(NotionTodoApiClientError):
    """Exception to indicate a missing resource."""


class NotionTodoApiClientRateLimitError(NotionTodoApiClientError):
    """Exception to indicate rate limiting."""


class NotionTodoApiClient:
    """Notion API client."""

    def __init__(self, token: str, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self._token = token
        self._session = session

    async def async_get_database(self, database_id: str) -> dict[str, Any]:
        """Fetch database metadata."""
        return await self._api_wrapper(
            method="get",
            url=f"{NOTION_API_BASE}/databases/{database_id}",
        )

    async def async_query_data_source(
        self, data_source_id: str
    ) -> list[dict[str, Any]]:
        """Query all pages for a data source."""
        results: list[dict[str, Any]] = []
        payload: dict[str, Any] = {"page_size": 100}
        next_cursor: str | None = None
        while True:
            if next_cursor:
                payload["start_cursor"] = next_cursor
            data = await self._api_wrapper(
                method="post",
                url=f"{NOTION_API_BASE}/data_sources/{data_source_id}/query",
                data=payload,
            )
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            next_cursor = data.get("next_cursor")
        return results

    async def async_search_databases(self) -> list[dict[str, Any]]:
        """Search for accessible databases."""
        results: list[dict[str, Any]] = []
        payload: dict[str, Any] = {
            "page_size": 100,
            "filter": {"property": "object", "value": "database"},
        }
        next_cursor: str | None = None
        while True:
            if next_cursor:
                payload["start_cursor"] = next_cursor
            data = await self._api_wrapper(
                method="post",
                url=f"{NOTION_API_BASE}/search",
                data=payload,
            )
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            next_cursor = data.get("next_cursor")
        return results

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an API request."""
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": NOTION_VERSION,
        }
        if method.lower() != "get":
            headers["Content-Type"] = "application/json"
        error: NotionTodoApiClientError | None = None
        try:
            async with asyncio.timeout(20):
                async with self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                ) as response:
                    if response.status in (401, 403):
                        error = NotionTodoApiClientAuthenticationError(
                            "Invalid credentials"
                        )
                    elif response.status == 400:
                        error = NotionTodoApiClientNotFoundError("Invalid database id")
                    elif response.status == 404:
                        error = NotionTodoApiClientNotFoundError("Resource not found")
                    elif response.status == 429:
                        error = NotionTodoApiClientRateLimitError("Rate limit exceeded")
                    else:
                        response.raise_for_status()
                        return await response.json()

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise NotionTodoApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise NotionTodoApiClientCommunicationError(msg) from exception
        except NotionTodoApiClientError:
            raise
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Unexpected error - {exception}"
            raise NotionTodoApiClientError(msg) from exception

        if error is not None:
            raise error

        raise NotionTodoApiClientError("Unexpected response")
