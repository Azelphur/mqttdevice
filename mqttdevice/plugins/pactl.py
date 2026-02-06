from enum import StrEnum
import glob
import json

import aiomqtt
from mqttdevice.device import Device
from mqttdevice.entities import BinarySensor, PluginConfig

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

import subprocess

class Config(PluginConfig):
    index: int
    metadata: dict

class Plugin(BinarySensor):
    device_class = BinarySensorDeviceClass.SOUND

    def get_discovery_payload(self):
        source = self.get_source(self.config["index"])
        payload = super().get_discovery_payload()
        # payload["json_attributes"] = list(source.keys())
        payload["json_attributes_topic"] = self.state_topic
        payload["json_attributes_template"] = "{{ value_json.metadata }}"
        return payload

    @staticmethod    
    def list_sources() -> list[dict]:
        try:
            result = subprocess.run(
                ["pactl", "-f", "json", "list", "sources"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True
            )
            sources = json.loads(result.stdout)

            return sources
        except Exception:
            pass

        return []
    
    @classmethod
    def get_source(cls, index: int) -> dict | None:
        sources = cls.list_sources()
        if sources:
            for source in sources:
                if source["index"] == index:
                    return source


    def get_state(self) -> tuple[bool | None, str | None]:
        source = self.get_source(self.config["index"])
        if source:
            return source["state"] == "RUNNING", source
        return None, None
    
    async def publish_state(self, client: aiomqtt.Client | None = None) -> None:
        client = client or self.client

        state, metadata = self.get_state()
        device_class = (self.device_class.value if isinstance(self.device_class, StrEnum) else self.device_class) or "state"
        payload = {device_class: self.format_state(state), "metadata": metadata}
        await client.publish(self.state_topic, json.dumps(payload), retain=True)
        self.logger.info(f"Published state: {json.dumps(payload)}")


def setup(device: Device, config: PluginConfig):
    for source in Plugin.list_sources():
        _config = Config(
            index=source["index"],
            metadata=source,
            id=f"{config['id']}_{source['name']}",
            name=source['description']
        )
        Plugin(device, _config)
