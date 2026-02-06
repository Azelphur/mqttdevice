from __future__ import annotations

from typing import TypedDict


class PluginConfig(TypedDict):
    id: str
    name: str | None
    plugin: str
    polling_interval: int | None
