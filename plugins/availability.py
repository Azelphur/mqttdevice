from mqttdevice import BinarySensor, MQTTDevice
import logging


class Plugin(BinarySensor):
    name = "available"

    def __init__(self, mqttdevice: MQTTDevice):
        self.mqttdevice: MQTTDevice = mqttdevice

    def get_state(self):
        return self.mqttdevice.connected


def setup(mqttdevice: MQTTDevice, config: any):
    plugin = Plugin(mqttdevice)
    mqttdevice.register_plugin(plugin)
    mqttdevice.will_set(plugin, "OFF")
