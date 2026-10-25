"""The read-only view of the TV's current Picture Mode — fed from this config entry's shared
PictureModeStream (coordinator.py), not its own connection. See coordinator.py for why the stream
is a persistent logcat connection rather than polling.

Restores its last known value across a Home Assistant restart (RestoreEntity) so it always shows
a value immediately, rather than "unknown" until the TV's log happens to report something — e.g.
right after HA restarts, before anyone has touched the Picture menu since."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_MEDIA_PLAYER, DOMAIN, MODE_UNKNOWN, SETTABLE_MODES
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
    async_add_entities([TvPictureModeSensor(entry, stream)])


class TvPictureModeSensor(SensorEntity, RestoreEntity):
    _attr_icon = "mdi:television-ambient-light"
    _attr_has_entity_name = True
    _attr_translation_key = "picture_mode"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, stream: PictureModeStream) -> None:
        self._stream = stream
        self._attr_unique_id = f"{entry.entry_id}_picture_mode"
        self._attr_device_info = _device_info(entry, entry.data[CONF_MEDIA_PLAYER])
        self._remove_listener = None

    @property
    def available(self) -> bool:
        return self._stream.available

    @property
    def native_value(self) -> str:
        return self._stream.current_mode

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Only seeds the shared stream state, and only if nothing live has reported a mode yet —
        # whichever of this entity / the select entity is added to hass first "wins" and the
        # other just sees the already-seeded value; a real log line from the stream always
        # overwrites this the moment one arrives.
        if self._stream.current_mode == MODE_UNKNOWN:
            last_state = await self.async_get_last_state()
            if last_state is not None and last_state.state in SETTABLE_MODES:
                self._stream.current_mode = last_state.state
        self._remove_listener = self._stream.add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
