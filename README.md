# Notion Todo

Home Assistant custom integration that surfaces Notion tasks as a Todo list.

## Install

- HACS (custom repo): add this repo, then install.
- Manual: copy `custom_components/notion_todo` into your HA config.

## Setup

1. Create a Notion internal integration and copy the token.
2. Share your task database with that integration.
3. Add **Notion Todo** in Home Assistant and enter:
   - Token
   - Database ID (or paste the full database URL)
   - If the database has multiple data sources, select one when prompted
   - Property names (optional)

Default property names:
- Title: `Name`
- Status: `Status`
- Due: `Due`
- Description: `Description`

Filtering:
- Include statuses: comma-separated (e.g. `Next`)
- Exclude statuses: comma-separated (e.g. `Someday, Inbox, Waiting, Dropped`)
- Include due within days: number of days (e.g. `7`)

## Notes

- Read-only for now (lists tasks only).
- Status mapping: any status containing "done" or "complete" is treated as completed.
- Uses Notion API version 2025-09-03 to support multi-source databases.
