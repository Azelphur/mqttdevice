from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar
import json
import typing
import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass


if typing.TYPE_CHECKING:
    from mqttdevice.entities import MQTTDevice

logger = logging.getLogger("mqttdevice")
logging.basicConfig(level=logging.INFO)


class Entity(ABC):
    name: ClassVar[str]
    domain: ClassVar[str]
    device_class: ClassVar[str | None] = None
    unit_of_measurement: ClassVar[str | None] = None

    _mqttdevice: MQTTDevice

    @classmethod
    def register(cls, mqttdevice: MQTTDevice, *args, **kwargs):
        instance = cls(*args, **kwargs)
        mqttdevice.register_plugin(instance)
        return instance

    def initialize_plugin(self, mqttdevice: MQTTDevice):
        self._mqttdevice = mqttdevice

    @property
    def mqttdevice(self) -> MQTTDevice:
        try:
            return self._mqttdevice
        except AttributeError:
            raise AttributeError("Plugin not initialized yet.")

    def publish_discovery(self):
        topic = self.get_topic()
        self.mqttdevice.client.publish(
            f"{topic}/config", json.dumps(self.get_publish_payload()), retain=True
        )
        logger.debug(f"Published discovery for {topic}")

    def get_topic(self):
        return f"{self.mqttdevice.get_discovery_prefix()}/{self.domain}/{self.mqttdevice.get_device_name()}_{self.name}"

    def get_publish_payload(self):
        topic = self.get_topic()

        payload = {
            "uniq_id": self.name,
            "state_topic": f"{topic}/state",
            "dev": self.mqttdevice.get_device_metadata(),
            "o": {
                "name": "MQTTDevice",
                "url": "https://github.com/Azelphur/mqttdevice",
            },
        }
        if self.device_class:
            payload["device_class"] = self.device_class
        if self.unit_of_measurement:
            payload["unit_of_measurement"] = self.unit_of_measurement
        logger.debug(f"Generated payload for {topic}: {payload}")
        return payload


class EntityWithState(Entity):
    @abstractmethod
    def get_state(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def publish_state(self) -> Any:
        raise NotImplementedError


class EntityWithMessage(Entity):
    @abstractmethod
    def on_message(self, payload) -> Any:
        raise NotImplementedError


class BinarySensor(EntityWithState, ABC):
    name = None
    domain = "binary_sensor"
    device_class: ClassVar[BinarySensorDeviceClass]

    def publish_state(self):
        topic = self.get_topic()
        payload = {"state": "ON" if self.get_state() else "OFF"}
        self.mqttdevice.client.publish(
            f"{topic}/state", json.dumps(payload), retain=True
        )
        logger.debug(f"Generated payload for {topic}: {payload}")


class Button(EntityWithMessage, ABC):
    name = None
    domain = "button"

    def publish_discovery(self):
        super().publish_discovery()
        topic = self.get_topic()
        self.mqttdevice.client.subscribe(f"{topic}/set")

    def get_publish_payload(self):
        topic = self.get_topic()
        return {
            "name": f"{self.mqttdevice.get_device_name()}_{self.name}",
            "command_topic": f"{topic}/set",
        }
