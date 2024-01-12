from mqttdevice import BinarySensor, MQTTDevice


class Plugin(BinarySensor):
    name = "available"

    def get_state(self):
        return True


def setup(mqttdevice: MQTTDevice, config: any):
    plugin = Plugin()
    mqttdevice.register_plugin(plugin)
    mqttdevice.will_set(plugin, "OFF")
