"""Diagnostics for Haier hOn: what pyhon loaded per appliance, secrets redacted."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pyhon.appliance import HonAppliance

from . import maintenance
from .const import CONF_REFRESH_TOKEN, DOMAIN

REDACTED = "**REDACTED**"
TO_REDACT = {
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    "access_token",
    "accessToken",
    "id_token",
    "idToken",
    "cognitoToken",
    "token",
    "tokenSigned",
    "unique_id",
    "macAddress",
    "mac",
    "serialNumber",
    "serial",
    "code",
    "coords",
    "lat",
    "lng",
    "latitude",
    "longitude",
    "PK",
    "SK",
    "SK_Secondary",
    "id",
    "applianceId",
    "eepromId",
    "mobileId",
    "nickName",
    "topics",
    "userId",
}
_MAC = re.compile(r"[0-9A-Fa-f]{2}([-:])[0-9A-Fa-f]{2}(\1[0-9A-Fa-f]{2}){4}")


def _plain(value: Any) -> Any:
    """JSON-safe copy; pyhon attributes become their values, MACs are masked."""
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return _MAC.sub(REDACTED, value) if isinstance(value, str) else value
    if hasattr(value, "value"):
        return _plain(value.value)
    return _MAC.sub(REDACTED, str(value))


def _settings(device: HonAppliance) -> dict[str, Any]:
    try:
        return {
            name: _plain(setting.value) for name, setting in device.settings.items()
        }
    except Exception as error:  # pylint: disable=broad-except
        return {"error": str(error)}


def _maintenance(device: HonAppliance) -> dict[str, Any]:
    last = maintenance.filter_last_replaced(device)
    check_up = maintenance.last_check_up(device)
    return {
        "carbon_filter_present": maintenance.has_carbon_filter(device),
        "carbon_filter_last_replaced": last.isoformat() if last else None,
        "carbon_filter_age_months": maintenance.filter_age_months(device),
        "carbon_filter_due": maintenance.filter_due(device),
        "carbon_filter_attributes": maintenance.filter_attributes(device),
        "check_up_present": maintenance.has_check_up(device),
        "last_check_up": check_up.isoformat() if check_up else None,
    }


def appliance_diagnostics(device: HonAppliance) -> dict[str, Any]:
    data = {
        "appliance_type": device.appliance_type,
        "model_name": device.model_name,
        "model_id": device.model_id,
        "zone": device.zone,
        "connection": device.connection,
        "info": _plain(device.info),
        "attributes": _plain(device.attributes),
        "commands": sorted(device.commands),
        "settings": _settings(device),
        "statistics": _plain(device.statistics),
        "maintenance": _maintenance(device),
    }
    redacted: dict[str, Any] = async_redact_data(data, TO_REDACT)
    return redacted


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    runtime = hass.data.get(DOMAIN, {}).get(entry.unique_id, {})
    appliances = runtime["hon"].appliances if "hon" in runtime else []
    refresher = runtime.get("maintenance")
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "maintenance_last_refresh": (
            refresher.last_refresh.isoformat() if refresher is not None else None
        ),
        "appliances": [appliance_diagnostics(device) for device in appliances],
    }
