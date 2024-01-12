from abc import ABC, abstractmethod
from typing import Any, ClassVar, Protocol
import importlib
import json
import paho.mqtt.client as mqtt
import asyncio
import logging
import sys
import subprocess
from types import ModuleType
from socket import gethostname

logger = logging.getLogger(__name__)


class Args(Protocol):
    device_name: str
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    discovery_prefix: str
    plugins: str


class WillAlreadySetError(Exception):
    pass


class MQTTDevice:
    def __init__(self, args):
        self.args: Args = args
        self.last_will = False
        if not args.plugins:
            logger.error("No plugins specified, nothing to do, exiting")
            sys.exit(1)
        self.entity_classes: dict[str, Entity] = dict()
        self.client: mqtt.Client = mqtt.Client(self.args.device_name)
        for plugin in args.plugins.split(","):
            try:
                plugin_module = importlib.import_module(f"plugins.{plugin}")
            except ModuleNotFoundError:
                logger.error(f"No such plugin {plugin}")
                sys.exit(1)
            plugin_instance = plugin_module.setup(self)
        self.client.username_pw_set(self.args.mqtt_username, self.args.mqtt_password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.connect(self.args.mqtt_host, self.args.mqtt_port)

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
            f"{self.args.discovery_prefix}/binary_sensor/{self.args.device_name}_available"
        ].publish_state()

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
        return f"{self._mqttdevice.args.discovery_prefix}/{self.domain}/{self._mqttdevice.args.device_name}_{self.name}"

    def get_publish_payload(self):
        topic = self.get_topic()
        return {
            "name": f"{self._mqttdevice.args.device_name}_{self.name}",
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
    parser.add_argument("--device_name", default=gethostname())
    parser.add_argument("--mqtt-host")
    parser.add_argument("--mqtt-port", type=int, default=1883, required=False)
    parser.add_argument("--mqtt-username")
    parser.add_argument("--mqtt-password")
    parser.add_argument("--discovery_prefix", default="homeassistant", required=False)
    parser.add_argument("--plugins", default="", required=False)
    args = parser.parse_args()
    m = MQTTDevice(args)
    m.loop_forever()
