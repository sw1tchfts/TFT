"""Global hotkeys for triggering captures while TFT has focus.

Default bindings map to capture sources:
    1..7  -> scout opponent N (snapshot tagged "opp1".."opp7")
    0     -> capture your own board/bench/shop ("self")
    `     -> reset the running pool tally

pynput is imported lazily so the pure modules stay importable without it.
"""

from __future__ import annotations

from typing import Callable

from ..engine.pool import OPPONENT_SOURCES, SELF_SOURCE

# Logical action ids.
RESET = "reset"


def default_bindings() -> dict[str, str]:
    """Map keyboard keys -> action ids."""
    bindings = {str(i): OPPONENT_SOURCES[i - 1] for i in range(1, 8)}  # 1..7
    bindings["0"] = SELF_SOURCE
    bindings["`"] = RESET
    return bindings


class HotkeyManager:
    """Listens for single-key presses and dispatches to a callback.

    on_action(action_id) is called with the bound action (an OPPONENT_SOURCES
    entry, SELF_SOURCE, or RESET). Designed to run while TFT is focused, so it
    uses a global listener rather than an app-window shortcut.
    """

    def __init__(self, on_action: Callable[[str], None],
                 bindings: dict[str, str] | None = None):
        self.on_action = on_action
        self.bindings = bindings or default_bindings()
        self._listener = None

    def _on_press(self, key):
        try:
            ch = key.char  # printable keys
        except AttributeError:
            return
        action = self.bindings.get(ch)
        if action is not None:
            self.on_action(action)

    def start(self):
        from pynput import keyboard  # lazy import

        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.start()
        return self._listener

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
