"""TFT Scout entry point.

Wires the trained recognizer, capture, pool engine, and dashboard together.

    python main.py                 # launch the dashboard (needs models/ trained)
    python main.py --cli           # headless: print the report to stdout

Process a saved screenshot file (for testing / calibration without the game):

    python main.py --image shot.png --source opp1   # recognize + print report
    python main.py --image shot.png --debug-crops out/  # dump each sliced slot

Before first launch:
    python -m src.data.fetch_data --set 17     # data + portraits
    python -m src.model.train --epochs 8       # train the recognizer
    python -m src.capture.calibrate            # set the capture region
"""

from __future__ import annotations

import argparse
import os

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(REPO_ROOT, "models", "classifier.pt")
LAYOUT_PATH = os.path.join(REPO_ROOT, "config", "layout_1024x768.json")


def _load_image(path: str):
    import numpy as np
    from PIL import Image

    return np.asarray(Image.open(path).convert("RGB"))


def _process_file(args) -> int:
    """Handle --image: optional debug crop dump, then recognize + report."""
    from src.capture.layout import Layout
    from src.capture.slicer import save_crops, slice_image

    image = _load_image(args.image)
    layout = Layout.load(LAYOUT_PATH)
    print(f"loaded {args.image} {image.shape[1]}x{image.shape[0]}; "
          f"region {layout.region}")

    # crop the layout region out of the full screenshot
    x0, y0, x1, y1 = layout.region
    if x1 > image.shape[1] or y1 > image.shape[0]:
        print("! the layout region is larger than the image. Recalibrate the "
              "region (python -m src.capture.calibrate) or use a full-size shot.")
        return 1
    region_image = image[y0:y1, x0:x1]

    if args.debug_crops:
        crops = slice_image(region_image, layout)  # all groups
        n = save_crops(crops, args.debug_crops)
        print(f"saved {n} slot crops to {args.debug_crops}/ "
              "-- open them to check the geometry lines up.")

    if not os.path.exists(MODEL_PATH):
        print("! no trained model found (models/classifier.pt). Run "
              "`python -m src.model.train` to enable recognition. "
              "Skipping recognition.")
        return 0

    from src.app.controller import build_controller
    from src.ui.render import format_row

    controller = build_controller(min_confidence=args.min_conf)
    event = controller.process_image(image, args.source)
    print(f"\n{args.source}: recognized {event.count} units")
    for u in event.units:
        print(f"  {u.api_name}  {u.star}*")

    print("\nReport (most contestable first):")
    for r in sorted(controller.report(), key=lambda r: (-r.held, r.cost))[:15]:
        print(" ", format_row(r))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cli", action="store_true",
                    help="print the report to stdout instead of launching the UI")
    ap.add_argument("--min-conf", type=float, default=0.5,
                    help="recognition confidence threshold (default 0.5)")
    ap.add_argument("--image", help="process a saved screenshot file")
    ap.add_argument("--source", default="opp1",
                    help="source tag for --image (opp1..opp7, self; default opp1)")
    ap.add_argument("--debug-crops", metavar="DIR",
                    help="with --image: save each sliced slot to DIR for "
                         "calibration checks")
    args = ap.parse_args(argv)

    if args.image:
        return _process_file(args)

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
