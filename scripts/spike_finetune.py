"""Throwaway spike: can this archive's own hand teach a recogniser anything?

Every pretrained model loses to the engine on this writing, and the standing
conclusion is that the archive needs its own training data. It has 152
labelled crops (`training_set.py`). This asks the only honest first question:
does fine-tuning on them move the character error at all, or is 152 simply too
few to say?

Held out: the six rows of BS_ENT_014541-p2, which is the page every other
model in `docs/TASKS-reading-quality.md` was scored on, so the number here
sits beside those. Six rows is a small held-out set and the result is a
direction, not a measurement.

    .venv-htr/bin/python scripts/spike_finetune.py --trainset data/trainset
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from spike_ocr import cer                              # noqa: E402

HELD_OUT = "BS_ENT_014541-p2.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trainset", type=Path, required=True)
    ap.add_argument("--model",
                    default="Riksarkivet/trocr-base-handwritten-hist-swe-2")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "spike_finetune.json")
    args = ap.parse_args()

    import torch
    from PIL import Image
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel

    rows = [json.loads(l) for l in
            (args.trainset / "labels.jsonl").open(encoding="utf-8")]
    train = [r for r in rows if r["source"] != HELD_OUT]
    test = [r for r in rows if r["source"] == HELD_OUT]
    if not test:
        raise SystemExit(f"nothing held out: no rows from {HELD_OUT}")
    print(f"{len(train)} to train on, {len(test)} held out", flush=True)

    proc = TrOCRProcessor.from_pretrained(args.model)
    model = VisionEncoderDecoderModel.from_pretrained(args.model)
    model.config.decoder_start_token_id = proc.tokenizer.cls_token_id or \
        model.config.decoder_start_token_id
    model.config.pad_token_id = proc.tokenizer.pad_token_id

    def images(batch):
        ims = [Image.open(args.trainset / r["image"]).convert("RGB") for r in batch]
        return proc(images=ims, return_tensors="pt").pixel_values

    def read(batch):
        model.eval()
        with torch.no_grad():
            ids = model.generate(images(batch), num_beams=4, max_new_tokens=32)
        return [t.strip() for t in proc.batch_decode(ids, skip_special_tokens=True)]

    def score(label: str) -> float:
        said = read(test)
        got = [cer(r["label"], s) for r, s in zip(test, said)]
        mean = sum(got) / len(got)
        print(f"  {label}: CER {mean:.3f}", flush=True)
        for r, s in zip(test, said):
            print(f"     {r['label']!r} -> {s!r}", flush=True)
        return mean

    before = score("before")

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    t0 = time.time()
    rng = random.Random(7)
    for epoch in range(args.epochs):
        model.train()
        order = train[:]
        rng.shuffle(order)
        total = 0.0
        for k in range(0, len(order), args.batch):
            chunk = order[k:k + args.batch]
            labels = proc.tokenizer([r["label"] for r in chunk],
                                    return_tensors="pt", padding=True).input_ids
            labels[labels == proc.tokenizer.pad_token_id] = -100
            loss = model(pixel_values=images(chunk), labels=labels).loss
            loss.backward()
            opt.step()
            opt.zero_grad()
            total += float(loss)
        print(f"epoch {epoch + 1}: loss {total / max(1, len(order)):.3f}, "
              f"{time.time() - t0:.0f}s", flush=True)

    after = score(f"after {args.epochs} epochs")
    args.out.write_text(json.dumps(
        {"model": args.model, "train": len(train), "held_out": len(test),
         "epochs": args.epochs, "lr": args.lr,
         "cer_before": round(before, 3), "cer_after": round(after, 3),
         "seconds": round(time.time() - t0, 1)}, indent=2))
    print(f"\nCER {before:.3f} -> {after:.3f} (engine reads this page at 0.205)")


if __name__ == "__main__":
    main()
