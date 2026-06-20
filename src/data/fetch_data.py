"""Fetch TFT champion data and portraits from CommunityDragon.

Generates `config/set_data.json` (champion list, costs, traits, pool sizes) and
downloads each champion's in-game HUD portrait into `assets/portraits/<set>/`.

CommunityDragon is a free, no-auth, community CDN that mirrors Riot's game
assets. The data file lists every TFT set; we select one set and emit a compact,
app-specific config. Pool sizes (copies-per-champion) are NOT in the source data
-- they are game constants supplied here and remain user-editable afterward.

Usage:
    python -m src.data.fetch_data --set 17
    python -m src.data.fetch_data --set 17 --version 15.13 --no-images
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

# Default copies-per-champion by cost. These are stable across most recent sets
# but can shift by patch, so they land in set_data.json for easy editing.
DEFAULT_POOL_SIZES = {1: 30, 2: 25, 3: 18, 4: 10, 5: 9}

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_DIR = os.path.join(REPO_ROOT, "config")
PORTRAIT_DIR = os.path.join(REPO_ROOT, "assets", "portraits")


def cdragon_base(version: str) -> str:
    return f"https://raw.communitydragon.org/{version}"


# CommunityDragon rejects the default Python user-agent with HTTP 403.
USER_AGENT = "tft-scout/0.1 (+https://github.com/sw1tchfts/tft)"


def http_get(url: str, retries: int = 4, timeout: int = 60) -> bytes:
    last = None
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # network hiccup -> exponential backoff
            last = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"failed to GET {url}: {last}")


def icon_to_png_path(icon: str) -> str:
    """Convert a game asset path like
    'ASSETS/Characters/TFT17_Briar/HUD/TFT17_Briar_Square.TFT_Set17.tex'
    into the CommunityDragon PNG sub-path."""
    p = icon.lower()
    for ext in (".tex", ".dds"):
        if p.endswith(ext):
            p = p[: -len(ext)] + ".png"
            break
    return "game/" + p


def select_set(data: dict, set_number: int) -> dict:
    """Pick the primary set entry (mutator 'TFTSet<n>') for a set number."""
    candidates = [s for s in data["setData"] if s.get("number") == set_number]
    if not candidates:
        raise SystemExit(f"set {set_number} not found in CommunityDragon data")
    primary = [s for s in candidates if s.get("mutator") == f"TFTSet{set_number}"]
    return (primary or candidates)[0]


def is_playable(champ: dict) -> bool:
    """Keep only rollable champions (cost 1-5 with traits)."""
    cost = champ.get("cost")
    return isinstance(cost, int) and 1 <= cost <= 5 and bool(champ.get("traits"))


def build_set_data(set_entry: dict, version: str, pool_sizes: dict[int, int]) -> dict:
    champions = []
    for c in set_entry["champions"]:
        if not is_playable(c):
            continue
        icon = c.get("tileIcon") or c.get("squareIcon") or ""
        portrait = f"{c['apiName'].lower()}.png"
        champions.append(
            {
                "apiName": c["apiName"],
                "name": c["name"],
                "cost": int(c["cost"]),
                "traits": list(c.get("traits", [])),
                "portrait": portrait,
                "_icon": icon,  # internal: used for image download, dropped on write
            }
        )
    champions.sort(key=lambda c: (c["cost"], c["name"]))
    return {
        "set": set_entry.get("number"),
        "mutator": set_entry.get("mutator"),
        "name": set_entry.get("name"),
        "source": "communitydragon",
        "source_version": version,
        "pool_sizes_by_cost": {str(k): v for k, v in pool_sizes.items()},
        "champions": champions,
    }


def download_portraits(set_data: dict, version: str) -> int:
    out_dir = os.path.join(PORTRAIT_DIR, f"set{set_data['set']}")
    os.makedirs(out_dir, exist_ok=True)
    base = cdragon_base(version)
    ok = 0
    for c in set_data["champions"]:
        icon = c.get("_icon")
        if not icon:
            print(f"  ! no icon for {c['apiName']}", file=sys.stderr)
            continue
        url = f"{base}/{icon_to_png_path(icon)}"
        dest = os.path.join(out_dir, c["portrait"])
        try:
            with open(dest, "wb") as fh:
                fh.write(http_get(url))
            ok += 1
        except Exception as exc:
            print(f"  ! failed {c['apiName']}: {exc}", file=sys.stderr)
    print(f"downloaded {ok}/{len(set_data['champions'])} portraits -> {out_dir}")
    return ok


def write_config(set_data: dict) -> str:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    # strip internal fields before writing
    clean = json.loads(json.dumps(set_data))
    for c in clean["champions"]:
        c.pop("_icon", None)
    path = os.path.join(CONFIG_DIR, "set_data.json")
    with open(path, "w") as fh:
        json.dump(clean, fh, indent=2)
        fh.write("\n")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--set", type=int, default=17, help="TFT set number (default 17)")
    ap.add_argument("--version", default="latest",
                    help="CommunityDragon version, e.g. 'latest' or '15.13'")
    ap.add_argument("--no-images", action="store_true", help="skip portrait download")
    args = ap.parse_args(argv)

    url = f"{cdragon_base(args.version)}/cdragon/tft/en_us.json"
    print(f"fetching {url} ...")
    data = json.loads(http_get(url))

    set_entry = select_set(data, args.set)
    set_data = build_set_data(set_entry, args.version, DEFAULT_POOL_SIZES)

    by_cost: dict[int, int] = {}
    for c in set_data["champions"]:
        by_cost[c["cost"]] = by_cost.get(c["cost"], 0) + 1
    print(f"set {args.set} ({set_data['name']}): {len(set_data['champions'])} "
          f"playable champions; by cost {dict(sorted(by_cost.items()))}")

    if not args.no_images:
        download_portraits(set_data, args.version)

    path = write_config(set_data)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
