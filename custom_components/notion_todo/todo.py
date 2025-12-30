"""Todo platform for Notion Todo."""

from __future__ import annotations

import datetime as dt
from typing import Any

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
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
)
from .coordinator import NotionTodoDataUpdateCoordinator
from .data import NotionTodoConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NotionTodoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Notion Todo list entities."""
    coordinator: NotionTodoDataUpdateCoordinator = entry.runtime_data.coordinator
    async_add_entities([NotionTodoListEntity(coordinator, entry)])


def _plain_text(parts: list[dict[str, Any]]) -> str:
    """Join Notion rich text parts into a string."""
    return "".join(part.get("plain_text", "") for part in parts).strip()


def _extract_text(prop: dict[str, Any] | None) -> str | None:
    """Extract text from a Notion property."""
    if not prop:
        return None
    prop_type = prop.get("type")
    if prop_type in ("title", "rich_text"):
        return _plain_text(prop.get(prop_type) or []) or None
    if prop_type == "select":
        select = prop.get("select")
        return select.get("name") if select else None
    return None


def _extract_due(prop: dict[str, Any] | None) -> dt.date | dt.datetime | None:
    """Extract due date/datetime from a Notion property."""
    if not prop or prop.get("type") != "date":
        return None
    date_value = prop.get("date") or {}
    start = date_value.get("start")
    if not start:
        return None
    if "T" in start:
        parsed = dt_util.parse_datetime(start)
        return dt_util.as_local(parsed) if parsed else None
    try:
        return dt.date.fromisoformat(start)
    except ValueError:
        return None


def _status_name(prop: dict[str, Any] | None) -> str | None:
    """Extract status/select name from a Notion property."""
    if not prop:
        return None
    prop_type = prop.get("type")
    if prop_type in ("status", "select"):
        value = prop.get(prop_type) or {}
        return value.get("name")
    return None


def _is_completed(prop: dict[str, Any] | None) -> bool:
    """Determine completion based on a Notion property."""
    if not prop:
        return False
    prop_type = prop.get("type")
    if prop_type == "checkbox":
        return bool(prop.get("checkbox"))
    if prop_type in ("status", "select"):
        value = prop.get(prop_type) or {}
        name = (value.get("name") or "").casefold()
        return (
            "done" in name
            or "complete" in name
            or "completed" in name
            or "dropped" in name
        )
    return False


def _parse_status_list(value: str | None) -> set[str]:
    """Parse a comma-separated list of statuses."""
    if not value:
        return set()
    return {item.strip().casefold() for item in value.split(",") if item.strip()}


def _get_entry_value(entry: NotionTodoConfigEntry, key: str, default: Any) -> Any:
    """Return config value from options or data."""
    if key in entry.options:
        return entry.options.get(key, default)
    return entry.data.get(key, default)


def _due_within_window(
    due: dt.date | dt.datetime | None, days: int
) -> bool:
    """Check if due is within the next N days."""
    if due is None or days <= 0:
        return False
    now = dt_util.now()
    if isinstance(due, dt.datetime):
        return due <= now + dt.timedelta(days=days)
    return due <= (now.date() + dt.timedelta(days=days))


class NotionTodoListEntity(
    CoordinatorEntity[NotionTodoDataUpdateCoordinator], TodoListEntity
):
    """Notion Todo list entity."""

    _attr_supported_features = 0

    def __init__(
        self,
        coordinator: NotionTodoDataUpdateCoordinator,
        entry: NotionTodoConfigEntry,
    ) -> None:
        """Initialize the todo list entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._database_id = entry.data[CONF_DATABASE_ID]
        self._title_property = entry.data.get(
            CONF_TITLE_PROPERTY, DEFAULT_TITLE_PROPERTY
        )
        self._status_property = entry.data.get(
            CONF_STATUS_PROPERTY, DEFAULT_STATUS_PROPERTY
        )
        self._due_property = entry.data.get(CONF_DUE_PROPERTY, DEFAULT_DUE_PROPERTY)
        self._description_property = entry.data.get(
            CONF_DESCRIPTION_PROPERTY, DEFAULT_DESCRIPTION_PROPERTY
        )
        self._include_statuses = _parse_status_list(
            _get_entry_value(entry, CONF_INCLUDE_STATUSES, DEFAULT_INCLUDE_STATUSES)
        )
        self._exclude_statuses = _parse_status_list(
            _get_entry_value(entry, CONF_EXCLUDE_STATUSES, DEFAULT_EXCLUDE_STATUSES)
        )
        self._due_within_days = int(
            _get_entry_value(entry, CONF_DUE_WITHIN_DAYS, DEFAULT_DUE_WITHIN_DAYS)
            or 0
        )
        self._attr_unique_id = f"{entry.entry_id}-{self._database_id}"
        self._attr_name = entry.title

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._include_statuses = _parse_status_list(
            _get_entry_value(
                self._entry, CONF_INCLUDE_STATUSES, DEFAULT_INCLUDE_STATUSES
            )
        )
        self._exclude_statuses = _parse_status_list(
            _get_entry_value(
                self._entry, CONF_EXCLUDE_STATUSES, DEFAULT_EXCLUDE_STATUSES
            )
        )
        self._due_within_days = int(
            _get_entry_value(
                self._entry, CONF_DUE_WITHIN_DAYS, DEFAULT_DUE_WITHIN_DAYS
            )
            or 0
        )
        pages = self.coordinator.data or []
        items: list[TodoItem] = []
        for page in pages:
            if page.get("archived") or page.get("in_trash"):
                continue
            props = page.get("properties", {})
            title = _extract_text(props.get(self._title_property)) or "Untitled"
            status_name = _status_name(props.get(self._status_property))
            completed = _is_completed(props.get(self._status_property))
            status = (
                TodoItemStatus.COMPLETED
                if completed
                else TodoItemStatus.NEEDS_ACTION
            )
            due = _extract_due(props.get(self._due_property))
            description = _extract_text(props.get(self._description_property))
            if self._exclude_statuses and status_name:
                if status_name.casefold() in self._exclude_statuses:
                    continue
            if self._include_statuses or self._due_within_days > 0:
                include_by_status = (
                    status_name.casefold() in self._include_statuses
                    if status_name and self._include_statuses
                    else False
                )
                include_by_due = _due_within_window(due, self._due_within_days)
                if not (include_by_status or include_by_due):
                    continue
            items.append(
                TodoItem(
                    summary=title,
                    uid=page.get("id"),
                    status=status,
                    due=due,
                    description=description or None,
                )
            )
        self._attr_todo_items = items
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass update state from existing data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
