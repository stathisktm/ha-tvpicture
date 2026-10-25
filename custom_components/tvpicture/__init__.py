
"""TV Picture Mode — reads and switches the TCL Android TV's on-screen Picture Mode (Standard,
Vivid, Sport, Movie, Smart) without root. The real hardware setting lives behind a HIDL interface
(vendor.realtek.tv@1.0::IRtkPQ) that adb shell can locate but is explicitly denied the
binder:transfer permission needed to actually call — confirmed live via logcat's own
`avc: denied` line — so there is no direct, invisible way to do this on this device at all.

Instead, this asks TvSettings itself to do it, through the voice-assistant hook in its
ShowWindowService (see _build_remote_script below) — one `adb shell` call that sets the preset
directly, no menu navigation or key presses.

The sensor this integration exposes is NOT updated from that call's result, though — it's fed by
its own persistent logcat stream (sensor.py), for the same reason tvchannel's MODE_LOGCAT_STREAM
sensor exists: that's the only way to also learn about a Picture Mode change made some other way,
most importantly with the physical remote, not only one made through this integration's own
set_mode action.
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_MODE,
    CONF_ADBKEY_PATH,
    CONF_HOST,
    CONF_PORT,
    DEFAULT_PORT,
    DISMISS_DELAY_S,
    DOMAIN,
    LABEL_BY_MODE,
    SERVICE_REFRESH,
    SERVICE_SET_MODE,
    SETTABLE_MODES,
)
from .coordinator import PictureModeStream

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT]

SET_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_MODE): vol.In(SETTABLE_MODES),
    },
)
REFRESH_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_ids})

# TvSettings' own voice-assistant entry point ("AI2.X SET" in ShowWindowService): Type=Settings +
# ITEM=picture_mode + MOTION=SET + MOTION_VALUE=<on-screen label> makes TvSettings (system uid,
# the only process SELinux lets call tcl_tv_display) set the preset directly — one call, no key
# presses. It then pops a small floating confirmation, closed right away with quickmenu.dismiss.
# An unknown MOTION_VALUE changes nothing but still logs "PictureMode = <current>", which the
# logcat stream picks up — that is how refresh reads the mode.
_SVC = "com.android.tv.settings/com.tcl.settings.ShowWindowService"


def _build_remote_script(target_mode: str | None) -> str:
    """target_mode=None means read-only: nothing changes, the current mode is just logged."""
    value = LABEL_BY_MODE.get(target_mode, "__read__") if target_mode else "__read__"
    return (
        f"am startservice -n {_SVC} -a com.tcl.settings.SHOW_WINDOW "
        f"--es Type Settings --es ITEM picture_mode --es MOTION SET --es MOTION_VALUE '{value}' >/dev/null; "
        f"sleep {DISMISS_DELAY_S}; "
        f"am startservice -n {_SVC} -a com.tcl.quickmenu.dismiss >/dev/null"
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    async def _run(entity_ids: list[str], target_mode: str | None) -> None:
        script = _build_remote_script(target_mode)

        for target in entity_ids:
            await hass.services.async_call(
                "androidtv",
                "adb_command",
                {
                    ATTR_ENTITY_ID: target,
                    "command": script,
                },
                blocking=True,
            )

            # The persistent logcat stream updates the sensor independently.
            # Do not update the sensor from the ADB response here.

    async def handle_set_mode(call: ServiceCall) -> None:
        await _run(call.data[ATTR_ENTITY_ID], call.data[ATTR_MODE])

    async def handle_refresh(call: ServiceCall) -> None:
        await _run(call.data[ATTR_ENTITY_ID], None)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MODE,
        handle_set_mode,
        schema=SET_MODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        handle_refresh,
        schema=REFRESH_SCHEMA,
    )

    # One persistent logcat connection per config entry, shared by all entities.
    stream = PictureModeStream(
        hass,
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
        entry.data.get(CONF_ADBKEY_PATH) or "",
    )
    stream.start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = stream

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unloaded:
        stream: PictureModeStream | None = hass.data.get(DOMAIN, {}).pop(
            entry.entry_id,
            None,
        )

        if stream is not None:
            stream.stop()

    return unloaded
