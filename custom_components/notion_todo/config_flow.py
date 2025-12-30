"""Adds config flow for Notion Todo."""

from __future__ import annotations

import re
import uuid
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    NotionTodoApiClient,
    NotionTodoApiClientAuthenticationError,
    NotionTodoApiClientCommunicationError,
    NotionTodoApiClientError,
    NotionTodoApiClientNotFoundError,
)
from .const import (
    CONF_DATA_SOURCE_ID,
    CONF_DATABASE_ID,
    CONF_DESCRIPTION_PROPERTY,
    CONF_DUE_PROPERTY,
    CONF_DUE_WITHIN_DAYS,
    CONF_EXCLUDE_STATUSES,
    CONF_INCLUDE_STATUSES,
    CONF_STATUS_PROPERTY,
    CONF_TITLE_PROPERTY,
    DEFAULT_DESCRIPTION_PROPERTY,
    DEFAULT_DUE_PROPERTY,
    DEFAULT_DUE_WITHIN_DAYS,
    DEFAULT_EXCLUDE_STATUSES,
    DEFAULT_INCLUDE_STATUSES,
    DEFAULT_STATUS_PROPERTY,
    DEFAULT_TITLE_PROPERTY,
    DOMAIN,
    LOGGER,
)


def _database_title(database: dict[str, Any]) -> str | None:
    """Extract database title."""
    title_parts = database.get("title", [])
    title = "".join(part.get("plain_text", "") for part in title_parts).strip()
    return title or None


def _data_sources(database: dict[str, Any]) -> list[dict[str, str]]:
    """Extract data source id/name pairs from a database payload."""
    sources: list[dict[str, str]] = []
    for source in database.get("data_sources") or []:
        source_id = source.get("id")
        if not source_id:
            continue
        sources.append(
            {
                "id": source_id,
                "name": str(source.get("name") or source.get("title") or ""),
            }
        )
    if database.get("data_source"):
        source = database.get("data_source") or {}
        source_id = source.get("id")
        if source_id and not any(s["id"] == source_id for s in sources):
            sources.append(
                {
                    "id": source_id,
                    "name": str(source.get("name") or source.get("title") or ""),
                }
            )
    return sources


_UUID_RE = re.compile(
    r"[0-9a-fA-F]{32}|"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
UNDASHED_UUID_LENGTH = 32


def _candidate_database_ids(value: str) -> list[str]:
    """Return candidate Notion database ids from a raw id or URL."""
    matches = _UUID_RE.findall(value)
    if not matches:
        return []
    candidates: list[str] = []
    for raw in matches:
        if raw not in candidates:
            candidates.append(raw)
        if "-" not in raw and len(raw) == UNDASHED_UUID_LENGTH:
            try:
                dashed = str(uuid.UUID(hex=raw))
            except ValueError:
                dashed = None
            if dashed and dashed not in candidates:
                candidates.append(dashed)
        elif "-" in raw:
            stripped = raw.replace("-", "")
            if stripped and stripped not in candidates:
                candidates.append(stripped)
    return candidates


class NotionTodoFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Notion Todo."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._pending_data: dict[str, Any] | None = None
        self._available_databases: list[dict[str, str]] | None = None
        self._available_data_sources: list[dict[str, str]] | None = None
        self._pending_database_title: str | None = None
        super().__init__()

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return NotionTodoOptionsFlowHandler(config_entry)

    def _errors_from_exception(
        self, exception: NotionTodoApiClientError
    ) -> dict[str, str]:
        if isinstance(exception, NotionTodoApiClientAuthenticationError):
            LOGGER.warning("Auth failed: %s", exception)
            return {"base": "auth"}
        if isinstance(exception, NotionTodoApiClientCommunicationError):
            LOGGER.error("Connection error: %s", exception)
            return {"base": "connection"}
        LOGGER.exception("Unexpected Notion error: %s", exception)
        return {"base": "unknown"}

    def _abort_from_exception(
        self, exception: NotionTodoApiClientError
    ) -> config_entries.ConfigFlowResult:
        if isinstance(exception, NotionTodoApiClientAuthenticationError):
            LOGGER.warning("Auth failed: %s", exception)
            return self.async_abort(reason="auth")
        if isinstance(exception, NotionTodoApiClientCommunicationError):
            LOGGER.error("Connection error: %s", exception)
            return self.async_abort(reason="connection")
        LOGGER.exception("Unexpected Notion error: %s", exception)
        return self.async_abort(reason="unknown")

    def _show_user_form(
        self, user_input: dict[str, Any] | None, errors: dict[str, str]
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TOKEN,
                        default=(user_input or {}).get(CONF_TOKEN, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                    vol.Required(
                        CONF_DATABASE_ID,
                        default=(user_input or {}).get(CONF_DATABASE_ID, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Optional(
                        CONF_TITLE_PROPERTY,
                        default=(user_input or {}).get(
                            CONF_TITLE_PROPERTY, DEFAULT_TITLE_PROPERTY
                        ),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Optional(
                        CONF_STATUS_PROPERTY,
                        default=(user_input or {}).get(
                            CONF_STATUS_PROPERTY, DEFAULT_STATUS_PROPERTY
                        ),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Optional(
                        CONF_DUE_PROPERTY,
                        default=(user_input or {}).get(
                            CONF_DUE_PROPERTY, DEFAULT_DUE_PROPERTY
                        ),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Optional(
                        CONF_DESCRIPTION_PROPERTY,
                        default=(user_input or {}).get(
                            CONF_DESCRIPTION_PROPERTY, DEFAULT_DESCRIPTION_PROPERTY
                        ),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Optional(
                        CONF_INCLUDE_STATUSES,
                        default=(user_input or {}).get(
                            CONF_INCLUDE_STATUSES, DEFAULT_INCLUDE_STATUSES
                        ),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Optional(
                        CONF_EXCLUDE_STATUSES,
                        default=(user_input or {}).get(
                            CONF_EXCLUDE_STATUSES, DEFAULT_EXCLUDE_STATUSES
                        ),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Optional(
                        CONF_DUE_WITHIN_DAYS,
                        default=(user_input or {}).get(
                            CONF_DUE_WITHIN_DAYS, DEFAULT_DUE_WITHIN_DAYS
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                },
            ),
            errors=errors,
        )

    async def _async_find_database(
        self, client: NotionTodoApiClient, candidates: list[str]
    ) -> tuple[dict[str, Any] | None, str | None]:
        database: dict[str, Any] | None = None
        selected_id: str | None = None
        for candidate_id in candidates:
            try:
                database = await client.async_get_database(candidate_id)
            except NotionTodoApiClientNotFoundError as exception:
                LOGGER.warning(
                    "Database not found for %s: %s",
                    candidate_id,
                    exception,
                )
                continue
            else:
                selected_id = candidate_id
                break
        return database, selected_id

    async def _async_handle_database_list(
        self, client: NotionTodoApiClient, user_input: dict[str, Any]
    ) -> config_entries.ConfigFlowResult | dict[str, str]:
        self._pending_data = user_input
        try:
            self._available_databases = await _list_databases(client=client)
        except NotionTodoApiClientError as exception:
            return self._errors_from_exception(exception)

        if self._available_databases:
            return await self.async_step_select()
        return {"base": "invalid_database"}

    async def _async_handle_database_selection(
        self,
        user_input: dict[str, Any],
        database: dict[str, Any],
        selected_id: str,
    ) -> config_entries.ConfigFlowResult | dict[str, str]:
        sources = _data_sources(database)
        if not sources:
            return {"base": "invalid_database"}
        if len(sources) == 1:
            user_input = {
                **user_input,
                CONF_DATABASE_ID: selected_id,
                CONF_DATA_SOURCE_ID: sources[0]["id"],
            }
            await self.async_set_unique_id(sources[0]["id"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=_database_title(database) or selected_id,
                data=user_input,
            )

        self._pending_data = {
            **user_input,
            CONF_DATABASE_ID: selected_id,
        }
        self._available_data_sources = sources
        self._pending_database_title = _database_title(database) or selected_id
        return await self.async_step_select_data_source()

    async def _async_handle_user_input(
        self, user_input: dict[str, Any]
    ) -> config_entries.ConfigFlowResult | dict[str, str]:
        candidates = _candidate_database_ids(user_input[CONF_DATABASE_ID])
        if not candidates:
            return {"base": "invalid_id"}

        client = NotionTodoApiClient(
            token=user_input[CONF_TOKEN],
            session=async_get_clientsession(self.hass),
        )
        try:
            database, selected_id = await self._async_find_database(client, candidates)
        except NotionTodoApiClientError as exception:
            return self._errors_from_exception(exception)

        if not database or not selected_id:
            return await self._async_handle_database_list(client, user_input)
        return await self._async_handle_database_selection(
            user_input, database, selected_id
        )

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self._show_user_form(user_input, {})

        result = await self._async_handle_user_input(user_input)
        if isinstance(result, dict) and "type" not in result:
            return self._show_user_form(user_input, result)
        return result

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select an accessible database."""
        if not self._pending_data or not self._available_databases:
            return self.async_abort(reason="no_databases")

        if user_input is None:
            options = [
                {
                    "value": item["id"],
                    "label": item["title"] or item["id"],
                }
                for item in self._available_databases
            ]
            return self.async_show_form(
                step_id="select",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_DATABASE_ID): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=options,
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                    }
                ),
            )

        selected = user_input[CONF_DATABASE_ID]
        client = NotionTodoApiClient(
            token=self._pending_data[CONF_TOKEN],
            session=async_get_clientsession(self.hass),
        )
        try:
            database = await client.async_get_database(selected)
        except NotionTodoApiClientError as exception:
            return self._abort_from_exception(exception)

        sources = _data_sources(database)
        if not sources:
            return self.async_abort(reason="invalid_database")
        if len(sources) == 1:
            data = {
                **self._pending_data,
                CONF_DATABASE_ID: selected,
                CONF_DATA_SOURCE_ID: sources[0]["id"],
            }
            await self.async_set_unique_id(sources[0]["id"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=_database_title(database) or selected,
                data=data,
            )

        self._pending_data = {
            **self._pending_data,
            CONF_DATABASE_ID: selected,
        }
        self._available_data_sources = sources
        self._pending_database_title = _database_title(database) or selected
        return await self.async_step_select_data_source()

    async def async_step_select_data_source(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select a data source for the database."""
        if not self._pending_data or not self._available_data_sources:
            return self.async_abort(reason="no_databases")

        if user_input is not None:
            selected = user_input[CONF_DATA_SOURCE_ID]
            data = {
                **self._pending_data,
                CONF_DATA_SOURCE_ID: selected,
            }
            await self.async_set_unique_id(selected)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._pending_database_title or data[CONF_DATABASE_ID],
                data=data,
            )

        options = [
            {
                "value": item["id"],
                "label": item["name"] or item["id"],
            }
            for item in self._available_data_sources
        ]
        return self.async_show_form(
            step_id="select_data_source",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DATA_SOURCE_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )


async def _list_databases(client: NotionTodoApiClient) -> list[dict[str, str]]:
    """Return accessible databases as id/title pairs."""
    results = await client.async_search_databases()
    databases: list[dict[str, str]] = []
    for item in results:
        if item.get("object") != "database":
            continue
        databases.append(
            {
                "id": item.get("id", ""),
                "title": _database_title(item) or "",
            }
        )
    return [db for db in databases if db["id"]]


class NotionTodoOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Notion Todo."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._config_entry.options
        data = self._config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_INCLUDE_STATUSES,
                        default=options.get(
                            CONF_INCLUDE_STATUSES,
                            data.get(CONF_INCLUDE_STATUSES, DEFAULT_INCLUDE_STATUSES),
                        ),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Optional(
                        CONF_EXCLUDE_STATUSES,
                        default=options.get(
                            CONF_EXCLUDE_STATUSES,
                            data.get(CONF_EXCLUDE_STATUSES, DEFAULT_EXCLUDE_STATUSES),
                        ),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Optional(
                        CONF_DUE_WITHIN_DAYS,
                        default=options.get(
                            CONF_DUE_WITHIN_DAYS,
                            data.get(CONF_DUE_WITHIN_DAYS, DEFAULT_DUE_WITHIN_DAYS),
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
