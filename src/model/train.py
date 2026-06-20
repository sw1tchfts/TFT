"""Train the champion+star classifier on synthetic data.

Usage:
    python -m src.model.train --epochs 8 --batch 128 --steps 200
    python -m src.model.train --smoke   # tiny run to validate the pipeline

Saves weights to models/classifier.pt and the label space to models/labels.json.
"""

from __future__ import annotations

import argparse
import os

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from .dataset import SyntheticDataset
from .labels import LabelSpace
from .net import ChampionNet
from .synth import SyntheticGenerator, default_portrait_dir

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_DIR = os.path.join(REPO_ROOT, "models")


def evaluate(model, loader, device, empty_index) -> dict:
    model.eval()
    champ_correct = total = star_correct = star_total = 0
    with torch.no_grad():
        for imgs, champ, star in loader:
            imgs = imgs.to(device)
            clogit, slogit = model(imgs)
            cpred = clogit.argmax(1).cpu()
            champ_correct += (cpred == champ).sum().item()
            total += champ.numel()
            # star accuracy only on non-empty targets
            mask = champ != empty_index
            if mask.any():
                spred = slogit.argmax(1).cpu()[mask]
                star_correct += (spred == star[mask]).sum().item()
                star_total += int(mask.sum())
    return {
        "champ_acc": champ_correct / max(total, 1),
        "star_acc": star_correct / max(star_total, 1),
    }


def train(epochs=8, batch=128, steps=200, size=64, lr=1e-3,
          width=32, seed=0, device=None) -> dict:
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    labels = LabelSpace.from_set_data()
    gen = SyntheticGenerator(labels, default_portrait_dir(17), size=size, seed=seed)
    train_ds = SyntheticDataset(gen, labels, length=batch * steps)
    eval_gen = SyntheticGenerator(labels, default_portrait_dir(17), size=size,
                                  seed=seed + 999)
    eval_ds = SyntheticDataset(eval_gen, labels, length=batch * max(2, steps // 10))
    train_loader = DataLoader(train_ds, batch_size=batch, num_workers=0)
    eval_loader = DataLoader(eval_ds, batch_size=batch, num_workers=0)

    model = ChampionNet(labels.num_classes, labels.num_stars, width=width).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    champ_loss = nn.CrossEntropyLoss()
    star_loss = nn.CrossEntropyLoss(reduction="none")

    metrics = {}
    for epoch in range(epochs):
        model.train()
        running = 0.0
        for imgs, champ, star in train_loader:
            imgs, champ, star = imgs.to(device), champ.to(device), star.to(device)
            clogit, slogit = model(imgs)
            lc = champ_loss(clogit, champ)
            # mask star loss for empty slots
            mask = (champ != labels.empty_index).float()
            ls_per = star_loss(slogit, star)
            ls = (ls_per * mask).sum() / mask.sum().clamp(min=1)
            loss = lc + 0.5 * ls
            opt.zero_grad()
            loss.backward()
            opt.step()
            running += loss.item()
        metrics = evaluate(model, eval_loader, device, labels.empty_index)
        print(f"epoch {epoch + 1}/{epochs}  loss={running / steps:.3f}  "
              f"champ_acc={metrics['champ_acc']:.3f}  star_acc={metrics['star_acc']:.3f}")

    os.makedirs(MODEL_DIR, exist_ok=True)
    weights_path = os.path.join(MODEL_DIR, "classifier.pt")
    torch.save(
        {
            "state_dict": model.state_dict(),
            "num_classes": labels.num_classes,
            "num_stars": labels.num_stars,
            "width": width,
            "size": size,
        },
        weights_path,
    )
    labels.save(os.path.join(MODEL_DIR, "labels.json"))
    print(f"saved {weights_path} and labels.json")
    return metrics


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--width", type=int, default=32)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--smoke", action="store_true",
                    help="tiny run to validate the pipeline end to end")
    args = ap.parse_args(argv)

    if args.smoke:
        train(epochs=1, batch=16, steps=4, width=8, size=64)
        return 0
    train(epochs=args.epochs, batch=args.batch, steps=args.steps, size=args.size,
          lr=args.lr, width=args.width, seed=args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
