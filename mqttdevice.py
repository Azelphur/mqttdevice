from abc import ABC, abstractmethod
from typing import Any, ClassVar, Protocol
import importlib
import json
import paho.mqtt.client as mqtt
import asyncio
import logging
import sys
import subprocess
import yaml
from types import ModuleType
from socket import gethostname

logger = logging.getLogger(__name__)


class WillAlreadySetError(Exception):
    pass


class MQTTDevice:
    def __init__(self, config: dict):
        self.config = config
        self.last_will = False
        self.entity_classes: dict[str, Entity] = dict()
        self.client: mqtt.Client = mqtt.Client(self.get_device_name())
        for plugin, plugin_config in config["plugins"].items():
            try:
                plugin_module = importlib.import_module(f"plugins.{plugin}")
            except ModuleNotFoundError:
                logger.error(f"No such plugin {plugin}")
                sys.exit(1)
            plugin_instance = plugin_module.setup(self, plugin_config)
        self.client.username_pw_set(
            self.config["mqtt_username"], self.config["mqtt_password"]
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.connect(
            self.config["mqtt_host"], self.config.get("mqtt_port", 1883)
        )

    def register_plugin(self, instance):
        instance.plugin_init(self)
        self.entity_classes[instance.get_topic()] = instance

    def loop_forever(self):
        self.client.loop_forever()

    def will_set(self, plugin, state):
        if self.last_will:
            raise WillAlreadySetError
        self.client.will_set(f"{plugin.get_topic()}/state", state, 0, False)
        self.last_will = True

    def on_connect(self, client, userdata, flags, rc):
        self.publish_discovery()
        self.publish_state()

    def on_disconnect(self, client, userdata, rc):
        self.plugins[
            f"{self.get_discovery_prefix()}/binary_sensor/{self.args.device_name}_available"
        ].publish_state()

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

    def plugin_init(self, mqttdevice):
        self._mqttdevice: MQTTDevice = mqttdevice

    def publish_discovery(self):
        topic = self.get_topic()
        self._mqttdevice.client.publish(
            f"{topic}/config", json.dumps(self.get_publish_payload()), retain=True
        )

    def get_topic(self):
        return f"{self._mqttdevice.get_discovery_prefix()}/{self.domain}/{self._mqttdevice.get_device_name()}_{self.name}"

    def get_publish_payload(self):
        topic = self.get_topic()
        return {
            "name": f"{self._mqttdevice.get_device_name()}_{self.name}",
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
        self._mqttdevice.client.publish(
            f"{topic}/state", "ON" if self.get_state() else "OFF", retain=True
        )


class Button(EntityWithMessage, ABC):
    name = None
    domain = "button"

    def publish_discovery(self):
        super().publish_discovery()
        topic = self.get_topic()
        self.client.subscribe(f"{topic}/set")

    def get_publish_payload(self):
        topic = self.get_topic()
        return {
            "name": f"{self._mqttdevice.args.device_name}_{self.name}",
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
    args = parser.parse_args()
    config = yaml.safe_load(args.config)
    m = MQTTDevice(config)
    m.loop_forever()
