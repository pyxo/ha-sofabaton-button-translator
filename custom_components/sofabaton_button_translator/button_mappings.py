"""The 68 Pyxo mappings; shared and immutable, never copied into settings."""

from types import MappingProxyType

_NAMES = (
    "up",
    "down",
    "left",
    "right",
    "ok",
    "return",
    "home",
    "menu",
    "volume_up",
    "volume_down",
    "mute",
    "channel_down",
    "channel_up",
    "rewind",
    "fast_forward",
    "dvr",
    "guide",
    "exit",
    "play",
    "pause",
    "a",
    "b",
    "c",
    "red",
    "green",
    "yellow",
    "blue",
)
DEFAULT_BUTTONS = MappingProxyType(
    dict(
        enumerate(
            [name for base in _NAMES for name in (base, f"{base}_long")]
            + [f"num_{n}" for n in range(10)]
            + ["num_dash", "num_e", "power_on", "power_off"],
            start=1,
        )
    )
)
