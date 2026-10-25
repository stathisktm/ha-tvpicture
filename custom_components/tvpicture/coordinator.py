"""The one persistent ADB/logcat connection a tvpicture config entry keeps open, fanned out to
however many entities subscribe to it (sensor.py, select.py) instead of each opening its own.

See const.py's LOGCAT_COMMAND comment for why this streams plain, unfiltered `logcat` and filters
for the Picture Mode line in Python instead of using `logcat -s <tag>` directly — confirmed live
that the tag-filtered form makes the adb_shell library's streaming_shell() end the stream after
about a second of silence (which this specific tag has constantly, since Picture Mode changes are
rare), while a plain `adb shell "logcat -s ..."` run directly never exits that way.

Self-healing: any disconnect (TV reboot, Wi-Fi blip, ...) is caught, logged, and retried after
RECONNECT_DELAY_S — indefinitely, for as long as this is running.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
import logging
import re

from homeassistant.core import HomeAssistant

from .const import (
    ANDROIDTV_ADBKEY_DIR,
    ANDROIDTV_ADBKEY_FILENAME,
    LOGCAT_COMMAND,
    MODE_BY_LOG_NAME,
    MODE_LOG_PATTERN,
    MODE_UNKNOWN,
    RECONNECT_DELAY_S,
)

_LOGGER = logging.getLogger(__name__)
_MODE_RE = re.compile(MODE_LOG_PATTERN)

# Generous on purpose — nothing is wrong with the connection just because the Picture menu hasn't
# been opened in a while; this only bounds how long a single streaming_shell() read can block
# before the library itself gives up and we go through the (harmless, self-healing) reconnect path.
_READ_TIMEOUT_S = 3600.0


def _load_or_generate_key(path: str):
    """Runs in an executor — file I/O and RSA key generation, neither belongs on the event loop.
    Generates a new key pair at [path] only if one doesn't already exist there; loading an
    existing one (the expected, common case: the androidtv integration's own key, already
    authorized on the TV) never touches the TV or needs any new on-screen confirmation."""
    import os

    from adb_shell.auth.keygen import keygen
    from adb_shell.auth.sign_pythonrsa import PythonRSASigner

    if not os.path.isfile(path):
        keygen(path)
    with open(path, encoding="utf-8") as f:
        private_key = f.read()
    with open(f"{path}.pub", encoding="utf-8") as f:
        public_key = f.read()
    return PythonRSASigner(public_key, private_key)


class PictureModeStream:
    """Owns the connection; current_mode/available are read directly by subscribed entities,
    which get notified (a plain sync callback, not an event) whenever either one changes."""

    def __init__(self, hass: HomeAssistant, host: str, port: int, adbkey_path: str) -> None:
        self.hass = hass
        self._host = host
        self._port = port
        self._adbkey_path = adbkey_path
        self.current_mode: str = MODE_UNKNOWN
        self.available: bool = False
        self._listeners: list[Callable[[], None]] = []
        self._task: asyncio.Task | None = None

    def add_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(callback)

        def _remove() -> None:
            self._listeners.remove(callback)

        return _remove

    def _notify(self) -> None:
        for callback in list(self._listeners):
            callback()

    def start(self) -> None:
        self._task = self.hass.async_create_background_task(self._run(), name="tvpicture_logcat")

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()

    async def _run(self) -> None:
        # Imported here, not at module level — this optional dependency being slow to install on
        # first setup shouldn't fail the rest of the integration from loading.
        from adb_shell.adb_device_async import AdbDeviceTcpAsync
        from adb_shell.exceptions import AdbCommandFailureException, TcpTimeoutException

        adbkey_path = self._adbkey_path or self.hass.config.path(ANDROIDTV_ADBKEY_DIR, ANDROIDTV_ADBKEY_FILENAME)
        try:
            rsa_keys = [await self.hass.async_add_executor_job(_load_or_generate_key, adbkey_path)]
        except Exception:  # noqa: BLE001 - a broken/unwritable key path is fatal for this stream, but not for HA
            _LOGGER.exception("tvpicture: could not load or generate an adb key at %s", adbkey_path)
            self.available = False
            self._notify()
            return

        buffer = ""
        while True:
            device = AdbDeviceTcpAsync(self._host, self._port, default_transport_timeout_s=9.0)
            try:
                # rsa_keys reuses the SAME key Home Assistant's own androidtv integration already
                # generated and got authorized on the TV by default — see const.py — so on a TV
                # already paired with that integration, this needs no new on-screen tap at all.
                await device.connect(rsa_keys=rsa_keys, auth_timeout_s=10.0)
                _LOGGER.debug("tvpicture: connected to %s:%s for logcat streaming", self._host, self._port)
                self.available = True
                self._notify()
                async for chunk in device.streaming_shell(
                    LOGCAT_COMMAND, transport_timeout_s=_READ_TIMEOUT_S, read_timeout_s=_READ_TIMEOUT_S,
                ):
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        match = _MODE_RE.search(line)
                        if match:
                            mode = MODE_BY_LOG_NAME.get(match.group(1), MODE_UNKNOWN)
                            if mode != self.current_mode:
                                self.current_mode = mode
                                self._notify()
            except asyncio.CancelledError:
                raise
            except (AdbCommandFailureException, TcpTimeoutException, OSError, EOFError) as err:
                _LOGGER.debug("tvpicture: logcat stream to %s:%s dropped (%s) — reconnecting in %ss",
                               self._host, self._port, err, RECONNECT_DELAY_S)
            except Exception:  # noqa: BLE001 - any other failure still just means "reconnect", never crash the task
                _LOGGER.exception("tvpicture: unexpected error streaming logcat from %s:%s", self._host, self._port)
            finally:
                self.available = False
                self._notify()
                with contextlib.suppress(Exception):
                    await device.close()
            await asyncio.sleep(RECONNECT_DELAY_S)
