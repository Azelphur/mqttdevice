from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfTime

from mqttdevice.device import Device
from mqttdevice.entities import PluginConfig
from mqttdevice.entities.sensor import Sensor


class Plugin(Sensor):
    default_name = "Uptime"
    device_class = SensorDeviceClass.DURATION
    unit_of_measurement = UnitOfTime.SECONDS

    def get_state(self) -> float:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])


def setup(device: Device, config: PluginConfig):
    Plugin(device, config)
