from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Literal

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, DOMAIN

from mqttdevice.entities.entity import EntityWithState


class BinarySensor(EntityWithState, ABC):
    domain = DOMAIN
    device_class: ClassVar[BinarySensorDeviceClass | None] = None

    def format_state(self, state: bool) -> Literal["ON", "OFF"]:
        return "ON" if state else "OFF"

    @abstractmethod
    def get_state(self) -> bool:
        raise NotImplementedError
