from typing import Any
from mqttdevice import MQTTDevice
from mqttdevice.entities import Button
import subprocess


class Plugin(Button):
    def __init__(self, command):
        self.name = command["name"]
        self.command = command["command"]

    def on_message(self, payload):
        subprocess.Popen(self.command, shell=True)


def setup(mqttdevice: MQTTDevice, config: Any):
    for command in config:
        Plugin.register(mqttdevice, command)
