from mqttdevice import Button, MQTTDevice
import subprocess


class Plugin(Button):
    def __init__(self, command):
        self.name = command["name"]
        self.command = command["command"]

    def on_message(self, payload):
        subprocess.Popen(self.command, shell=True)


def setup(mqttdevice: MQTTDevice, config: any):
    for command in config:
        plugin = Plugin(command)
        mqttdevice.register_plugin(plugin)
