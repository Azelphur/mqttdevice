import json
import aiomqtt
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

    async def on_connect(self, client: aiomqtt.Client):
        await super().on_connect(client)
        device_class = (self.device_class.value if isinstance(self.device_class, SensorDeviceClass) else self.device_class) or "state"
        self.will_set(
            self.state_topic,
            json.dumps({device_class: 0}),
            retain=True,
        )

def setup(device: Device, config: PluginConfig):
    Plugin(device, config)
