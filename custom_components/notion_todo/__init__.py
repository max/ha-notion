"""
Custom integration to integrate Notion tasks with Home Assistant.

For more details about this integration, please refer to
https://github.com/max/ha-notion
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import NotionTodoApiClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER
from .coordinator import NotionTodoDataUpdateCoordinator
from .data import NotionTodoConfigEntry, NotionTodoData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.TODO]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NotionTodoConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    coordinator = NotionTodoDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )
    coordinator.config_entry = entry
    entry.runtime_data = NotionTodoData(
        client=NotionTodoApiClient(
            token=entry.data[CONF_TOKEN],
            session=async_get_clientsession(hass),
        ),
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: NotionTodoConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: NotionTodoConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
