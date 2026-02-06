from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from mqttdevice.device import Device
from mqttdevice.entities import BinarySensor, PluginConfig


class Plugin(BinarySensor):
    device_class = BinarySensorDeviceClass.CONNECTIVITY

    def get_state(self) -> bool:
        return True


def setup(device: Device, config: PluginConfig):
    Plugin(device, config)
