"""Constants for the TV Picture Mode integration."""

DOMAIN = "tvpicture"

CONF_MEDIA_PLAYER = "media_player_entity_id"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_ADBKEY_PATH = "adbkey_path"

DEFAULT_PORT = 5555

SERVICE_SET_MODE = "set_mode"
SERVICE_REFRESH = "refresh"

ATTR_MODE = "mode"

MODE_VIVID = "vivid"
MODE_STANDARD = "standard"
MODE_SPORT = "sport"
MODE_MOVIE = "movie"
MODE_SMART = "smart"
MODE_UNKNOWN = "unknown"

# All five are selectable — the TV's own quick-toggle cycle reaches all of them (confirmed live),
# so there's no reason to hide any from the select entity / set_mode service.
SETTABLE_MODES = [MODE_VIVID, MODE_STANDARD, MODE_SPORT, MODE_MOVIE, MODE_SMART]

# The real internal English name TCL's own Picture settings screen logs for each preset
# (com.tcl.settings.viewmodel.picture.PicturePresetScrollerLayoutVM, tag
# "PicturePresetScrollerLayoutVM") — confirmed live via logcat, both on opening the menu
# ("PictureMode = VIVID") and on every single selection change ("set index = 2,pictureMode  =
# STANDARD" / "newPictureMode = STANDARD"). Deliberately NOT the on-screen Greek label (e.g.
# "Δυναμική") — these English names are logged regardless of the TV's display language, and
# reading them is what lets this integration learn a Picture Mode change made any other way too
# (the physical remote, a different app, ...), not only one made through this integration's own
# set_mode action — see sensor.py's persistent logcat stream.
#
# Also the TV's own left/right quick-toggle cycle order, confirmed the same way: DPAD_RIGHT
# increases the index (mod CYCLE_LENGTH), DPAD_LEFT decreases it, both wrap around. Filmmaker/Game
# aren't in this cycle at all — the real remote only offers them when the current signal's own
# metadata supports them, so there is nothing to automate for those two beyond what the TV itself
# already restricts.
MODE_BY_LOG_NAME: dict[str, str] = {
    "SDR_AI_ADAP": MODE_SMART,
    "VIVID": MODE_VIVID,
    "STANDARD": MODE_STANDARD,
    "STADIUM": MODE_SPORT,
    "STUDIO": MODE_MOVIE,
}
CYCLE_INDEX: dict[str, int] = {
    MODE_SMART: 0,
    MODE_VIVID: 1,
    MODE_STANDARD: 2,
    MODE_SPORT: 3,
    MODE_MOVIE: 4,
}
CYCLE_LENGTH = len(CYCLE_INDEX)

# The on-screen preset names, which is what TvSettings' voice SET path matches MOTION_VALUE
# against (case-insensitive) — confirmed live via its "AI2.X SET valueArray = [Έξυπνο, Δυναμική,
# Τυπική, ΣΠΟΡ, Ταινία]" log line, in the order [SDR_AI_ADAP, VIVID, STANDARD, STADIUM, STUDIO].
# These follow the TV's display language: change them if the TV is switched away from Greek.
LABEL_BY_MODE: dict[str, str] = {
    MODE_SMART: "Έξυπνο",
    MODE_VIVID: "Δυναμική",
    MODE_STANDARD: "Τυπική",
    MODE_SPORT: "ΣΠΟΡ",
    MODE_MOVIE: "Ταινία",
}

# The SET pops a small floating confirmation; it's dismissed this long after.
DISMISS_DELAY_S = 0.3

# Home Assistant's own androidtv integration generates (if missing) and reuses an ADB key pair at
# exactly this path, shared across every androidtv config entry — see tvchannel's const.py for the
# same reasoning. Reusing it here means no new "Allow USB debugging?" tap on a TV already paired
# with that integration.
ANDROIDTV_ADBKEY_DIR = ".storage"
ANDROIDTV_ADBKEY_FILENAME = "androidtv_adbkey"

# Streamed continuously (not polled) for the same reason tvchannel's MODE_LOGCAT_STREAM is: it's
# the only way to learn about a Picture Mode change made some other way than this integration's
# own set_mode/refresh actions — most importantly, one made with the physical remote — without
# ever having to open the Picture menu on a timer just to check.
#
# Deliberately UNFILTERED (not `logcat -s PicturePresetScrollerLayoutVM:D`), and filtered for the
# tag in Python instead (see MODE_LOG_PATTERN below) — confirmed live that the tag-filtered form
# makes the adb_shell library's streaming_shell() end the stream (StopAsyncIteration) after about
# a second of silence, which this tag has constantly, since Picture Mode changes are rare. A plain
# `adb shell "logcat -s ..."` run directly never exits this way (confirmed live, blocked for 6s by
# `timeout` instead), so this is specifically a streaming_shell()-over-sparse-output behavior, not
# a logcat behavior — avoided entirely by always having non-stop (unfiltered) output to read.
LOGCAT_COMMAND = "logcat"
MODE_LOG_PATTERN = r"[Pp]ictureMode\s*=\s*([A-Z_]+)"

RECONNECT_DELAY_S = 15
