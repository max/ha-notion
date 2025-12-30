"""DataUpdateCoordinator for notion_todo."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    NotionTodoApiClientAuthenticationError,
    NotionTodoApiClientError,
    NotionTodoApiClientNotFoundError,
)
from .const import CONF_DATA_SOURCE_ID

if TYPE_CHECKING:
    from .data import NotionTodoConfigEntry


class NotionTodoDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Class to manage fetching data from the API."""

    config_entry: NotionTodoConfigEntry

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Update data via API."""
        try:
            data_source_id = self.config_entry.data.get(CONF_DATA_SOURCE_ID)
            if not data_source_id:
                raise UpdateFailed("Missing data source id; reconfigure integration.")
            return await self.config_entry.runtime_data.client.async_query_data_source(
                data_source_id
            )
        except NotionTodoApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except NotionTodoApiClientNotFoundError as exception:
            raise UpdateFailed(exception) from exception
        except NotionTodoApiClientError as exception:
            raise UpdateFailed(exception) from exception
