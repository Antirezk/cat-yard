"""Coding with Kirby — a desktop pet that lives on your screen while you code."""

from __future__ import annotations

import logging
import sys

from PyQt5.QtWidgets import QApplication
from core.main_controller import MainController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    controller = MainController(app)

    def on_quit() -> None:
        controller.stop_all_timers()
        controller.save_state()

    app.aboutToQuit.connect(on_quit)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
