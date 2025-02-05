from typing import Any
from mqttdevice import BinarySensor, MQTTDevice
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

class Plugin(BinarySensor):
    name = "available"
    device_class = BinarySensorDeviceClass.CONNECTIVITY

    def get_state(self) -> bool:
        return self.mqttdevice.client.is_connected()


def setup(mqttdevice: MQTTDevice, config: Any):
    plugin = Plugin.register(mqttdevice)
    mqttdevice.will_set(plugin, "OFF")
