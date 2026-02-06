from __future__ import annotations

import asyncio
import importlib
import json
import logging
import sys
import typing
import uuid
from socket import gethostname

import aiomqtt
from caseconverter import snakecase, titlecase

from mqttdevice.mqtt_object import MQTTConfig, MQTTObject

if typing.TYPE_CHECKING:
    from mqttdevice.entities import Entity

logger = logging.getLogger("mqttdevice.device")


class Config(typing.TypedDict):
    plugins: dict[str, typing.Any]
    mqtt: MQTTConfig


class Device(MQTTObject):
    def __init__(self, config: Config):
        self.config = config
        super().__init__(config.get("mqtt", MQTTConfig()))

        self.entities: dict[str, Entity] = dict()
        for plugin_config in config["plugins"]:
            plugin = plugin_config["plugin"]
            try:
                plugin_module = importlib.import_module(f"mqttdevice.plugins.{plugin}")
            except ModuleNotFoundError:
                logger.error(f"No such plugin {plugin}")
                sys.exit(1)
            plugin_module.setup(self, plugin_config)

    def register_plugin(self, instance: Entity) -> typing.Self:
        instance.initialize_plugin(self)
        self.entities[instance.identifier] = instance
        logger.info(f"Registered plugin {instance.identifier}")
        return self

    @property
    def polling_interval(self) -> int:
        return int(self.config.get("polling_interval", 60))

    @property
    def verbose_name(self) -> str:
        return self.config.get("device_name", titlecase(gethostname()))

    @property
    def name(self):
        return snakecase(self.verbose_name)

    @property
    def identifier(self) -> str:
        return self.name

    @property
    def device_metadata(self):
        return {
            "ids": [gethostname(), uuid.getnode()],
            "name": self.verbose_name,
        }

    def get_availability_state(self) -> bool:
        return self.client._client.is_connected()

    @property
    def availability_topic(self):
        return f"mqttdevice/{self.name}/availability"

    async def publish_availability_state(self, client: aiomqtt.Client | None = None):
        client = client or self.client
        payload = {"state": "online" if self.get_availability_state() else "offline"}
        await client.publish(self.availability_topic, json.dumps(payload), retain=True)
        self.logger.info(f"Published state: {json.dumps(json.dumps(payload))}")

    async def on_connect(self, client: aiomqtt.Client):
        await self.publish_availability_state(client)
        self.will_set(
            self.availability_topic,
            json.dumps({"state": "offline"}),
            retain=True,
        )

    async def on_loop(self, client: aiomqtt.Client):
        await self.publish_availability_state(client)

    async def on_disconnect(self):
        pass

    async def loop(self):
        print(f"Starting loop for {self.identifier}")
        async with self.client as client:
            await self.on_connect(client)
            while True:
                self.logger.debug(f"Running loop for {self.identifier}")
                await asyncio.sleep(self.polling_interval)
                self.logger.debug(f"Running loop for {self.identifier}")
                await self.on_loop(client)
