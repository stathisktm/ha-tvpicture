"""Config flow for TV Picture Mode."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .const import (
    ANDROIDTV_ADBKEY_DIR,
    ANDROIDTV_ADBKEY_FILENAME,
    CONF_ADBKEY_PATH,
    CONF_HOST,
    CONF_MEDIA_PLAYER,
    CONF_PORT,
    DEFAULT_PORT,
    DOMAIN,
)


def _schema(hass, defaults: dict[str, Any]) -> vol.Schema:
    default_adbkey_path = hass.config.path(ANDROIDTV_ADBKEY_DIR, ANDROIDTV_ADBKEY_FILENAME)
    return vol.Schema(
        {
            vol.Required(CONF_MEDIA_PLAYER, default=defaults.get(CONF_MEDIA_PLAYER)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="media_player"),
            ),
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Optional(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535),
            ),
            vol.Optional(
                CONF_ADBKEY_PATH,
                default=defaults.get(CONF_ADBKEY_PATH, default_adbkey_path),
            ): str,
        },
    )


class TvPictureConfigFlow(ConfigFlow, domain=DOMAIN):
    """One TV per config entry — the adb-capable media_player entity, plus the TV's own IP address
    (needed because the live state comes from this integration's own direct ADB connection, kept
    open to stream logcat, rather than going through the androidtv integration's one-shot
    adb_command — see sensor.py)."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_MEDIA_PLAYER])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_MEDIA_PLAYER], data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema(self.hass, user_input or {}))
