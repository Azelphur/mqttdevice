from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar
import importlib
import json
import typing
import paho.mqtt.client as mqtt
import logging
import sys
import yaml
from socket import gethostname

if typing.TYPE_CHECKING:
    from plugins.commands import Plugin

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class WillAlreadySetError(Exception):
    pass


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

    def publish_discovery(self):
        for entity in self.entity_classes.values():
            entity.publish_discovery()

    def publish_state(self):
        for topic, sensor_class in self.entity_classes.items():
            if hasattr(sensor_class, "publish_state"):
                sensor_class.publish_state()
                logger.debug(f"Published state for {topic}")

    def on_message(self, client, userdata, msg):
        print("Message received-> " + msg.topic + " " + str(msg.payload))
        payload = msg.payload.decode("utf-8")
        topic = msg.topic[:-4]
        if topic not in self.entity_classes:
            logger.error(f"{topic} not found")
            return
        self.entity_classes[topic].on_message(payload)


class Entity(ABC):
    name: ClassVar[str]
    domain: ClassVar[str]
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
        return {
            "name": f"{self.mqttdevice.get_device_name()}_{self.name}",
            "state_topic": f"{topic}/state",
        }


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

    def publish_state(self):
        topic = self.get_topic()
        self.mqttdevice.client.publish(
            f"{topic}/state", "ON" if self.get_state() else "OFF", retain=True
        )


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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="./config.yaml",
        help="Config file",
        type=argparse.FileType("r"),
        required=False,
    )
    parser.add_argument('-v', '--verbose',
                    action='store_true')
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    config = yaml.safe_load(args.config)
    m = MQTTDevice(config)
    m.loop_forever()
