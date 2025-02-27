from enum import StrEnum
import glob
import json

import aiomqtt
from mqttdevice.device import Device
from mqttdevice.entities import BinarySensor, PluginConfig

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

import subprocess

class Config(PluginConfig):
    device_path: str


class Plugin(BinarySensor):
    device_class = BinarySensorDeviceClass.RUNNING

    def get_discovery_payload(self):
        payload = super().get_discovery_payload()
        payload["json_attributes_topic"] = self.state_topic
        payload["json_attributes_template"] = "{{ value_json.metadata }}"
        return payload


    def get_state(self) -> tuple[bool | None, str | None]:
        path = self.config["device_path"]
        try:
            result = subprocess.run(
                ["lsof", "-w", path],  # -w suppresses warnings
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,  # Suppress unwanted errors
                text=True
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:  # First line is headers, subsequent lines are processes
                process_info = lines[1].split()
                return True, process_info[0]  # Process name
        except Exception as e:
            return None, None

        return False, None
    
    async def publish_state(self, client: aiomqtt.Client | None = None) -> None:
        client = client or self.client

        state, metadata = self.get_state()
        device_class = (self.device_class.value if isinstance(self.device_class, StrEnum) else self.device_class) or "state"
        payload = {device_class: self.format_state(state), "metadata": metadata}
        await client.publish(self.state_topic, json.dumps(payload), retain=True)
        self.logger.info(f"Published state: {json.dumps(payload)}")


def setup(device: Device, config: PluginConfig):
    for path in glob.glob("/dev/video*"):
        suffix = path.lstrip("/dev/video")
        _config = Config(device_path=path, id=f"{config['id']}_{suffix}", name=f"Webcam {path}")
        Plugin(device, _config)
