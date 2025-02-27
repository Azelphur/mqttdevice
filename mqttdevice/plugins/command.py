import subprocess

from aiomqtt.client import Message

from mqttdevice.device import Device
from mqttdevice.entities import Button, PluginConfig


class Config(PluginConfig):
    command: str


class Plugin(Button):
    def __init__(self, device: Device, config: Config):
        self.command = config["command"]
        super().__init__(device, config)

    async def on_message(self, message: Message):
        subprocess.Popen(self.command, shell=True)


def setup(device: Device, config: Config):
    Plugin(device, config)
