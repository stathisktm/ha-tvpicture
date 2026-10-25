"""A select entity so any Picture Mode can be picked directly from this integration's device card
or a dashboard, instead of only through the set_mode service — this is the one other entity fed
from this config entry's shared PictureModeStream (coordinator.py), alongside sensor.py. Picking
an option calls the exact same tvpicture.set_mode service the direct service-call path uses, so
there is exactly one way this integration ever actually changes the TV's Picture Mode.

Restores its last known option across a Home Assistant restart (RestoreEntity) so it always shows
a value immediately, rather than "unknown" until the TV's log happens to report something — see
sensor.py's identical restore logic for why this seeds the *shared* stream state, not just this
one entity's own display.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import ATTR_MODE, CONF_MEDIA_PLAYER, DOMAIN, MODE_UNKNOWN, SERVICE_SET_MODE, SETTABLE_MODES
from .coordinator import PictureModeStream


def _device_info(entry: ConfigEntry, media_player: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"TV Picture Mode ({media_player})",
        manufacturer="pestpoint",
        model="tvpicture",
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    stream: PictureModeStream = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TvPictureModeSelect(entry, stream)])


class TvPictureModeSelect(SelectEntity, RestoreEntity):
    _attr_icon = "mdi:television-ambient-light"
    _attr_has_entity_name = True
    _attr_translation_key = "picture_mode"
    _attr_should_poll = False
    _attr_options = SETTABLE_MODES

    def __init__(self, entry: ConfigEntry, stream: PictureModeStream) -> None:
        self._stream = stream
        self._media_player = entry.data[CONF_MEDIA_PLAYER]
        self._attr_unique_id = f"{entry.entry_id}_picture_mode_select"
        self._attr_device_info = _device_info(entry, self._media_player)
        self._remove_listener = None

    @property
    def available(self) -> bool:
        return self._stream.available

    @property
    def current_option(self) -> str | None:
        mode = self._stream.current_mode
        return mode if mode in SETTABLE_MODES else None

    async def async_select_option(self, option: str) -> None:
        await self.hass.services.async_call(
            DOMAIN, SERVICE_SET_MODE, {ATTR_ENTITY_ID: self._media_player, ATTR_MODE: option}, blocking=True,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Only seeds the shared stream state, and only if nothing live has reported a mode yet —
        # whichever of this entity / the sensor entity is added to hass first "wins" and the other
        # just sees the already-seeded value; a real log line from the stream always overwrites
        # this the moment one arrives.
        if self._stream.current_mode == MODE_UNKNOWN:
            last_state = await self.async_get_last_state()
            if last_state is not None and last_state.state in SETTABLE_MODES:
                self._stream.current_mode = last_state.state
        self._remove_listener = self._stream.add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
