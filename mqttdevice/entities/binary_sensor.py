from __future__ import annotations

import json
from abc import ABC
from typing import ClassVar

import aiomqtt
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, DOMAIN

from mqttdevice.entities.entity import EntityWithState


class BinarySensor(EntityWithState, ABC):
    domain = DOMAIN
    device_class: ClassVar[BinarySensorDeviceClass | None] = None

    async def publish_state(self, client: aiomqtt.Client | None = None):
        client = client or self.client
        payload = {self.device_class.value: "ON" if self.get_state() else "OFF"}
        await client.publish(self.state_topic, json.dumps(payload), retain=True)
        self.logger.info(f"Published state: {payload}")
