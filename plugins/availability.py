from typing import Any
from mqttdevice import BinarySensor, MQTTDevice


class Plugin(BinarySensor):
    name = "available"

    def get_state(self):
        return True


def setup(mqttdevice: MQTTDevice, config: Any):
    plugin = Plugin.register(mqttdevice)
    mqttdevice.will_set(plugin, "OFF")
