"""Unit tests for utils.telemetry_pubkey_prefix.

Regression coverage for remote telemetry being filed under the companion node:
meshcore_py pushes a reply to ``send_telemetry_req`` (as sent by the
execute_command service) with the sender in ``pubkey_pre``, while a polled
``req_telemetry`` reply carries ``pubkey_prefix``. Both telemetry handlers read
only ``pubkey_prefix``, so a pushed reply from a remote sensor fell through to
the self-telemetry branch and created its sensors on the companion device.

utils.py is loaded directly from file via importlib (mirroring
test_extract_pubkey_hex.py) so the real implementation is exercised rather than
the conftest MagicMock stub.
"""
import importlib.util
import os
import sys
from unittest.mock import MagicMock

import pytest

# Stub HA and integration modules that utils.py imports but aren't installed.
for _mod in (
    "homeassistant",
    "homeassistant.util",
    "homeassistant.util.slugify",
    "custom_components",
    "custom_components.meshcore",
    "custom_components.meshcore.const",
):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Provide slugify as an attribute so `from homeassistant.util import slugify` works.
sys.modules["homeassistant.util"].slugify = lambda x: x

_MESHCORE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "custom_components", "meshcore",
)
_UTILS_PATH = os.path.join(_MESHCORE_DIR, "utils.py")
_spec = importlib.util.spec_from_file_location(
    "custom_components.meshcore.utils", _UTILS_PATH
)
_module = importlib.util.module_from_spec(_spec)
_module.__package__ = "custom_components.meshcore"
_spec.loader.exec_module(_module)

telemetry_pubkey_prefix = _module.telemetry_pubkey_prefix


_LPP = [{"channel": 2, "type": "wind speed", "value": 0.0}]


def test_polled_reply_uses_pubkey_prefix():
    """A req_telemetry reply names the sender in pubkey_prefix."""
    payload = {"pubkey_prefix": "d54a78690307", "lpp": _LPP}
    assert telemetry_pubkey_prefix(payload) == "d54a78690307"


def test_pushed_reply_uses_pubkey_pre():
    """Regression: a send_telemetry_req reply names the sender in pubkey_pre."""
    payload = {"pubkey_pre": "d54a78690307", "lpp": _LPP}
    assert telemetry_pubkey_prefix(payload) == "d54a78690307"


def test_pubkey_prefix_wins_over_pubkey_pre():
    payload = {"pubkey_prefix": "d54a78690307", "pubkey_pre": "7f86dfb3234d", "lpp": _LPP}
    assert telemetry_pubkey_prefix(payload) == "d54a78690307"


@pytest.mark.parametrize("payload", [
    {"lpp": _LPP},                                      # neither key
    {"pubkey_prefix": "", "pubkey_pre": "", "lpp": _LPP},
    {"pubkey_prefix": None, "lpp": _LPP},
])
def test_missing_prefix_returns_empty_string(payload):
    """No sender collapses to '', which the handlers treat as self telemetry."""
    assert telemetry_pubkey_prefix(payload) == ""


def test_telemetry_handlers_use_helper():
    """Both TELEMETRY_RESPONSE handlers must route through the helper."""
    for fname in ("telemetry_sensor.py", "device_tracker.py"):
        with open(os.path.join(_MESHCORE_DIR, fname), encoding="utf-8") as fh:
            src = fh.read()
        assert 'event.payload.get("pubkey_prefix"' not in src, (
            f"{fname} still reads only pubkey_prefix from the telemetry payload"
        )
        assert "telemetry_pubkey_prefix(event.payload)" in src, (
            f"{fname} does not route through telemetry_pubkey_prefix"
        )
