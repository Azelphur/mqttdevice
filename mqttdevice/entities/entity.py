from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar, Self

import aiomqtt
from aiomqtt.client import Message

from mqttdevice.entities.config import PluginConfig
from mqttdevice.mqtt_object import MQTTObject

if TYPE_CHECKING:
    from mqttdevice.device import Device


class Entity(MQTTObject, ABC):
    default_name: ClassVar[str | None] = None
    config: PluginConfig
    domain: ClassVar[str]
    device_class: ClassVar[StrEnum | str | None] = None
    unit_of_measurement: ClassVar[StrEnum | str | None] = None

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
        return self.config.get("name", self.default_name)

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
            if isinstance(self.device_class, StrEnum):
                payload["device_class"] = self.device_class.value
            else:
                payload["device_class"] = self.device_class
        if self.unit_of_measurement:
            if isinstance(self.unit_of_measurement, StrEnum):
                payload["unit_of_measurement"] = self.unit_of_measurement.value
            else:
                payload["unit_of_measurement"] = self.unit_of_measurement
        return payload

    async def on_connect(self, client: aiomqtt.Client):
        await self.publish_discovery(client)

    async def on_loop(self, client: aiomqtt.Client):
        pass

    async def on_disconnect(self, client: aiomqtt.Client):
        pass

    async def loop(self):
        print("Starting loop")
        async with self.client as client:
            await self.on_connect(client)
            while True:
                self.logger.debug(f"Sleeping for {self.polling_interval} seconds")
                await asyncio.sleep(self.polling_interval)
                self.logger.debug("Running loop")
                await self.on_loop(client)
            await self.on_disconnect(client)


class EntityWithState(Entity, ABC):
    @abstractmethod
    def get_state(self) -> Any:
        raise NotImplementedError
    
    def format_state(self, state: Any) -> Any:
        return state

    @property
    def state_topic(self):
        device_class = (self.device_class.value if isinstance(self.device_class, StrEnum) else self.device_class) or "state"
        return f"mqttdevice/{self.identifier}/{device_class}"

    def get_discovery_payload(self):
        payload = super().get_discovery_payload()
        payload["state_topic"] = self.state_topic
        payload["value_template"] = self.value_template
        return payload

    @property
    def value_template(self):
        device_class = (self.device_class.value if isinstance(self.device_class, StrEnum) else self.device_class) or "state"
        return f"{{{{ value_json.{device_class} }}}}"
    
    async def publish_state(self, client: aiomqtt.Client | None = None) -> None:
        client = client or self.client
        device_class = (self.device_class.value if isinstance(self.device_class, StrEnum) else self.device_class) or "state"
        payload = {device_class: self.format_state(self.get_state())}
        await client.publish(self.state_topic, json.dumps(payload), retain=True)
        self.logger.info(f"Published state: {payload}")

    async def on_connect(self, client: aiomqtt.Client):
        await super().on_connect(client)
        await self.publish_state(client)

    async def on_loop(self, client: aiomqtt.Client):
        await super().on_loop(client)
        await self.publish_state(client)

    async def on_disconnect(self, client: aiomqtt.Client):
        await super().on_disconnect(client)
        await self.publish_state(client)


class EntityWithMessage(Entity, ABC):
    @abstractmethod
    async def on_message(self, message: Message) -> Any: ...

    async def loop(self):
        async with self.client as client:
            await self.on_connect(client)
            async for message in client.messages:
                await self.on_message(message)
