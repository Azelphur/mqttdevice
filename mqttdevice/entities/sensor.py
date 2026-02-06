from __future__ import annotations

from abc import ABC
from typing import ClassVar

from homeassistant.components.sensor import SensorDeviceClass, DOMAIN

from mqttdevice.entities.entity import EntityWithState


class Sensor(EntityWithState, ABC):
    domain = DOMAIN
    device_class: ClassVar[SensorDeviceClass | None] = None
