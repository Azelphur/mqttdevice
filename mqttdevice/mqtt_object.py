from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TypedDict

import aiomqtt
from aiomqtt.client import PayloadType, Properties

from mqttdevice.exceptions import WillAlreadySetError

logger = logging.getLogger("mqttdevice")


class MQTTConfig(TypedDict):
    host: str
    port: int | None
    username: str
    password: str


class MQTTObject(ABC):
    def __init__(self, config: MQTTConfig):
        self._mqtt_config = config

        self.logger = logging.getLogger(f"{logger.name}.{self.identifier}")
        self.logger.info("Starting MQTT Device")

        self.connected = False
        self.client: aiomqtt.Client = self._get_client()

    @property
    def last_will(self) -> bool:
        return self.client._client._will

    def _get_client(self) -> aiomqtt.Client:
        return aiomqtt.Client(
            hostname=self._mqtt_config["host"],
            port=self._mqtt_config.get("port", 1883),
            username=self._mqtt_config["username"],
            password=self._mqtt_config["password"],
            logger=self.logger,
            identifier=self.identifier,
        )

    @property
    @abstractmethod
    def identifier(self) -> str: ...

    def will_set(
        self,
        topic: str,
        payload: PayloadType = None,
        qos: int = 0,
        retain: bool = False,
        properties: Properties | None = None,
    ):
        if self.last_will:
            raise WillAlreadySetError
        self.client._client.will_set(topic, payload, qos, retain, properties)

    @abstractmethod
    async def on_connect(self): ...

    @abstractmethod
    async def on_disconnect(self): ...
