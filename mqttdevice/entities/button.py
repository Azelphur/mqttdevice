from __future__ import annotations

from abc import ABC
from typing import ClassVar

import aiomqtt
from homeassistant.components.button import ButtonDeviceClass, DOMAIN

from mqttdevice.entities.entity import EntityWithMessage


class Button(EntityWithMessage, ABC):
    domain = DOMAIN
    device_class: ClassVar[ButtonDeviceClass | None] = None

    @property
    def set_topic(self):
        return f"mqttdevice/{self.identifier}/set"

    async def publish_discovery(self, client: aiomqtt.Client | None = None):
        client = client or self.client
        await super().publish_discovery(client)
        await client.subscribe(self.set_topic)

    def get_discovery_payload(self):
        payload = super().get_discovery_payload()
        payload["command_topic"] = self.set_topic
        return payload
