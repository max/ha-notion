"""Custom types for notion_todo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import NotionTodoApiClient
    from .coordinator import NotionTodoDataUpdateCoordinator


type NotionTodoConfigEntry = ConfigEntry[NotionTodoData]


@dataclass
class NotionTodoData:
    """Data for the Notion Todo integration."""

    client: NotionTodoApiClient
    coordinator: NotionTodoDataUpdateCoordinator
    integration: Integration
