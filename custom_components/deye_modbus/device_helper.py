"""Shared DeviceInfo builder.

Controls are grouped into sub-devices that mirror the pages of the Deye Cloud
batch-command configurator (Battery Setting, System Work Mode, Grid setting,
SmartLoad Setting, Advanced Function, Time of Use). Sensors stay on the main
inverter device; each sub-device is linked to it with via_device.
"""
from __future__ import annotations

import re

from homeassistant.const import CONF_HOST
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, CONF_MODEL
from .models import get_model


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def build_device_info(entry, group: str | None = None) -> DeviceInfo:
    host = entry.data.get(CONF_HOST)
    model = get_model(entry.data.get(CONF_MODEL))
    base_name = f"Deye {model['model']}"
    if not group:
        return DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=base_name,
            manufacturer=model["manufacturer"],
            model=model["model"],
            configuration_url=(f"http://{host}" if host else None),
        )
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{_slug(group)}")},
        name=f"{base_name} {group}",
        manufacturer=model["manufacturer"],
        model=model["model"],
        via_device=(DOMAIN, entry.entry_id),
    )
