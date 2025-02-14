from __future__ import annotations

import importlib
import typing
import paho.mqtt.client as mqtt
import logging
import sys
import uuid
from socket import gethostname

from mqttdevice.exceptions import WillAlreadySetError


if typing.TYPE_CHECKING:
    from mqttdevice.entities import Entity
    from mqttdevice.plugins.commands import Plugin

logger = logging.getLogger("mqttdevice")
logging.basicConfig(level=logging.INFO)


class MQTTDevice:
    def __init__(self, config: dict):
        logger.info("Starting MQTT Device")

        self.config = config
        self.connected = False
        self.last_will = False
        self.entity_classes: dict[str, Entity] = dict()
        self.client: mqtt.Client = mqtt.Client(self.get_device_name())
        for plugin, plugin_config in config["plugins"].items():
            try:
                plugin_module = importlib.import_module(f"plugins.{plugin}")
            except ModuleNotFoundError:
                logger.error(f"No such plugin {plugin}")
                sys.exit(1)
            plugin_module.setup(self, plugin_config)
        self.client.username_pw_set(
            self.config["mqtt_username"], self.config["mqtt_password"]
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.connect(
            self.config["mqtt_host"], self.config.get("mqtt_port", 1883)
        )

    def register_plugin(self, instance: Plugin):
        instance.initialize_plugin(self)
        self.entity_classes[instance.get_topic()] = instance
        logger.info(f"Registered plugin {instance.get_topic()}")

    def loop_forever(self):
        logger.info("Starting loop")
        self.client.loop_forever()

    def will_set(self, plugin: Plugin, state):
        if self.last_will:
            raise WillAlreadySetError
        self.client.will_set(f"{plugin.get_topic()}/state", state, 0, False)
        self.last_will = True

    def on_connect(self, client, userdata, flags, rc):
        self.connected = True
        self.publish_discovery()
        self.publish_state()

    def on_disconnect(self, client, userdata, rc):
        self.connected = False
        self.publish_state()

    def get_discovery_prefix(self):
        return self.config.get("discovery_prefix", "homeassistant")

    def get_device_name(self):
        return self.config.get("device_name", gethostname())

    def get_device_metadata(self):
        return {
            "ids": [gethostname(), uuid.getnode()],
            "name": self.get_device_name(),
        }

    def publish_discovery(self):
        for entity in self.entity_classes.values():
            entity.publish_discovery()

    def publish_state(self):
        for topic, sensor_class in self.entity_classes.items():
            if hasattr(sensor_class, "publish_state"):
                sensor_class.publish_state()
                logger.debug(f"Published state for {topic}")

    def on_message(self, client, userdata, msg):
        logger.info("Message received-> " + msg.topic + " " + str(msg.payload))
        payload = msg.payload.decode("utf-8")
        topic = msg.topic[:-4]
        if topic not in self.entity_classes:
            logger.error(f"{topic} not found")
            return
        self.entity_classes[topic].on_message(payload)
