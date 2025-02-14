from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from enum import StrEnum
from typing import Any, ClassVar, Self, TypedDict
import json
import typing

import aiomqtt
from aiomqtt.client import Message
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from mqttdevice.mqtt_object import MQTTObject


if typing.TYPE_CHECKING:
    from mqttdevice.device import Device


class PluginConfig(TypedDict):
    id: str
    name: str | None
    plugin: str
    polling_interval: int | None


class Entity(MQTTObject, ABC):
    config: PluginConfig
    domain: ClassVar[str]
    device_class: ClassVar[StrEnum | None] = None
    unit_of_measurement: ClassVar[str | None] = None

    _device: Device

    def __init__(self, device: Device, config: PluginConfig, *args, **kwargs):
        self.config = config
        device.register_plugin(self)
        super().__init__(self.device._mqtt_config, *args, **kwargs)

    @property
    def id(self) -> str:
        return self.config["id"].lower()

    @property
    def name(self) -> str | None:
        return self.config.get("name")

    @property
    def identifier(self) -> str:
        return f"{self.device.name}_{self.id}"

    @property
    def polling_interval(self) -> int:
        return int(self.config.get("polling_interval", self.device.polling_interval))

    def initialize_plugin(self, device: Device) -> Self:
        self._device = device
        return self

    @property
    def device(self) -> Device:
        try:
            return self._device
        except AttributeError:
            raise AttributeError("Plugin not initialized yet.")

    async def publish_discovery(self, client: aiomqtt.Client | None = None):
        client = client or self.client
        payload = self.get_discovery_payload()
        self.logger.debug(f"Publishing discovery: {payload}")
        await client.publish(self.discovery_topic, json.dumps(payload), retain=True)
        self.logger.info("Published discovery")

    @property
    def discovery_topic(self):
        return f"homeassistant/{self.domain}/{self.device.name}/{self.id}/config"

    def get_discovery_payload(self):
        # Uses https://www.home-assistant.io/integrations/mqtt/#single-component-discovery-payload
        payload = {
            "availability": [
                {
                    "topic": f"mqttdevice/{self.device.name}/availability",
                    "value_template": "{{ value_json.state }}",
                }
            ],
            "availability_mode": "latest",
            "unique_id": self.id,
            "object_id": self.identifier,
            "dev": self.device.device_metadata,
            "o": {
                "name": "MQTTDevice",
                "url": "https://github.com/Azelphur/mqttdevice",
            },
        }
        if self.name:
            payload["name"] = self.name
        if self.device_class:
            payload["device_class"] = self.device_class.value
        if self.unit_of_measurement:
            payload["unit_of_measurement"] = self.unit_of_measurement
        return payload

    async def on_connect(self, client: aiomqtt.Client):
        await self.publish_discovery(client)

    async def on_loop(self, client: aiomqtt.Client):
        pass

    async def on_disconnect(self, client: aiomqtt.Client):
        pass

    async def loop(self):
        print(f"Starting loop")
        async with self.client as client:
            await self.on_connect(client)
            while True:
                self.logger.debug(f"Sleeping for {self.polling_interval} seconds")
                await asyncio.sleep(self.polling_interval)
                self.logger.debug(f"Running loop")
                await self.on_loop(client)
            await self.on_disconnect(client)


class EntityWithState(Entity):
    @abstractmethod
    def get_state(self) -> bool:
        raise NotImplementedError

    @property
    def state_topic(self):
        return f"mqttdevice/{self.identifier}/{self.device_class}"

    def get_discovery_payload(self):
        payload = super().get_discovery_payload()
        payload["state_topic"] = self.state_topic
        payload["value_template"] = self.value_template
        return payload

    @property
    def value_template(self):
        return f"{{{{ value_json.{self.device_class} }}}}"

    @abstractmethod
    async def publish_state(self, client: aiomqtt.Client | None = None) -> Any:
        raise NotImplementedError

    async def on_connect(self, client: aiomqtt.Client):
        await super().on_connect(client)
        await self.publish_state(client)

    async def on_loop(self, client: aiomqtt.Client):
        await super().on_loop(client)
        await self.publish_state(client)

    async def on_disconnect(self, client: aiomqtt.Client):
        await super().on_disconnect(client)
        await self.publish_state(client)


class EntityWithMessage(Entity):
    @abstractmethod
    async def on_message(self, message: Message) -> Any: ...

    async def loop(self):
        async with self.client as client:
            await self.on_connect(client)
            async for message in client.messages:
                await self.on_message(message)


class BinarySensor(EntityWithState, ABC):
    domain = "binary_sensor"
    device_class: ClassVar[BinarySensorDeviceClass]

    async def publish_state(self, client: aiomqtt.Client | None = None):
        client = client or self.client
        payload = {self.device_class.value: "ON" if self.get_state() else "OFF"}
        await client.publish(self.state_topic, json.dumps(payload), retain=True)
        self.logger.info(f"Published state: {payload}")


class Button(EntityWithMessage, ABC):
    domain = "button"

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
