"""TFT Scout entry point.

Wires the trained recognizer, capture, pool engine, and dashboard together.

    python main.py                 # launch the dashboard (needs models/ trained)
    python main.py --cli           # headless: print the report to stdout
    python main.py --min-conf 0.6  # tune recognition confidence threshold

Before first launch:
    python -m src.data.fetch_data --set 17     # data + portraits
    python -m src.model.train --epochs 8       # train the recognizer
    python -m src.capture.calibrate            # set the capture region
"""

from __future__ import annotations

import argparse


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cli", action="store_true",
                    help="print the report to stdout instead of launching the UI")
    ap.add_argument("--min-conf", type=float, default=0.5,
                    help="recognition confidence threshold (default 0.5)")
    args = ap.parse_args(argv)

    from src.app.controller import build_controller

    controller = build_controller(min_confidence=args.min_conf)

    if args.cli:
        from src.ui.render import format_report

        print(format_report(controller.report()))
        return 0

    from src.ui.dashboard import run_dashboard

    return run_dashboard(controller)


if __name__ == "__main__":
    raise SystemExit(main())
