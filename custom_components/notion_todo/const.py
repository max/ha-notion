"""Constants for notion_todo."""

from datetime import timedelta
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "notion_todo"
ATTRIBUTION = "Data provided by Notion"

CONF_DATABASE_ID = "database_id"
CONF_DATA_SOURCE_ID = "data_source_id"
CONF_INCLUDE_STATUSES = "include_statuses"
CONF_EXCLUDE_STATUSES = "exclude_statuses"
CONF_DUE_WITHIN_DAYS = "due_within_days"
CONF_TITLE_PROPERTY = "title_property"
CONF_STATUS_PROPERTY = "status_property"
CONF_DUE_PROPERTY = "due_property"
CONF_DESCRIPTION_PROPERTY = "description_property"

DEFAULT_TITLE_PROPERTY = "Name"
DEFAULT_STATUS_PROPERTY = "Status"
DEFAULT_DUE_PROPERTY = "Due"
DEFAULT_DESCRIPTION_PROPERTY = "Description"
DEFAULT_INCLUDE_STATUSES = ""
DEFAULT_EXCLUDE_STATUSES = ""
DEFAULT_DUE_WITHIN_DAYS = 0

NOTION_VERSION = "2025-09-03"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
