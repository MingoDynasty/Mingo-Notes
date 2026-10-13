"""Screenshot format/quality comparison harness.

Encodes a sample of the vault's 4K PNG originals at several format/quality
settings, measures what matters for this site, and emits a single self-contained
HTML page for eyeballing the results at 100% pixel scale.

This exists because the Phase 1 format decision (AVIF q80 4:4:4 over WebP) could
not be made from file sizes alone: lossy WebP's mandatory 4:2:0 chroma
desaturates Valorant's thin green crosshair at *every* quality, and that is
invisible in any aggregate metric. Seeing the crops side by side, toggled in
place, is what settled it.

Keep it for the next format question rather than the last one -- when JPEG XL
reaches universal browser support, or a quality bump is proposed, add a variant
to VARIANTS and re-run instead of rebuilding this from scratch.

Usage (from this directory, using the import script's venv):

    python format_pilot.py                      # 6 largest originals, default variants
    python format_pilot.py --count 10
    python format_pilot.py --images "Pasted image 20250601120000.png,Pasted image 20250602130000.png"
    python format_pilot.py --out ../../ignore/format-pilot

--images takes filenames exactly as they are in the source directory, paste
prefix included. The console and the report drop that prefix, so a name copied
from a heading needs it put back.

Output is written outside git (repo root `ignore/` is gitignored). The HTML is
self-contained -- crops are inlined -- so it can be copied anywhere and opened
years later without the source images.
"""
from __future__ import annotations

import argparse
import base64
import io
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from PIL import Image

# The vault is the source of truth for originals; the repo only ever holds
# derived assets. Override with --source if the vault moves.
DEFAULT_SOURCE = Path(r"E:\Obsidian\Vaults\My Vault\attachments")
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "ignore" / "format-pilot"

# Obsidian's paste prefix; stripped from display names only.
PASTE_PREFIX = "Pasted image "

# Native-pixel crop size for the displayed tiles. Big enough to show the
# crosshair and its surroundings, small enough that inlining
# n_images * n_variants * n_regions of them stays sane.
CROP = 360

# The window the crosshair metric is measured over. Deliberately much tighter
# than the display crop: a wide window pulls in green scenery, which compresses
# perfectly well and dilutes the very signal being measured. Measured on one
# frame, widening 160 -> 360 px admitted 46 px of foliage and dragged the
# lossless baseline from 255.0 down to 241.1, understating the gap between
# 4:4:4 and 4:2:0 by roughly a third.
MEASURE = 160


@dataclass(frozen=True)
class Variant:
    """One encoder setting under test.

    `label` is what appears in the UI; `fmt` and `params` go straight to
    PIL's Image.save. `reference` marks the lossless baseline every other
    variant is scored against.
    """

    label: str
    fmt: str
    params: dict[str, object] = field(default_factory=dict)
    reference: bool = False


# The shipped setting is first among the lossy variants so it reads as the
# default. 4:2:0 AVIF is included deliberately: it is the control that proves
# the chroma subsampling -- not the codec -- is what saves the crosshair.
VARIANTS: list[Variant] = [
    Variant("PNG original", "PNG", reference=True),
    Variant("AVIF q80 4:4:4 (shipped)", "AVIF", {"quality": 80, "subsampling": "4:4:4", "speed": 6}),
    Variant("AVIF q60 4:4:4", "AVIF", {"quality": 60, "subsampling": "4:4:4", "speed": 6}),
    Variant("AVIF q80 4:2:0", "AVIF", {"quality": 80, "subsampling": "4:2:0", "speed": 6}),
    Variant("WebP q90", "WEBP", {"quality": 90, "method": 6}),
]


@dataclass
class Measurement:
    """What one variant did to one image."""

    variant: str
    size_bytes: int
    encode_seconds: float
    crosshair_green: float
    crops: dict[str, str]  # region name -> base64 PNG data URI


def crop_regions(size: tuple[int, int]) -> dict[str, tuple[int, int, int, int]]:
    """Where to look on a 16:9 gameplay capture.

    Centre is the crosshair -- the reference a lineup is actually aimed with.
    The lower-right corner carries the ammo counter, and the lower-left the
    ability icons; both are used to confirm a lineup's preconditions, so they
    have to survive compression too.
    """
    w, h = size
    half = CROP // 2
    return {
        "crosshair": (w // 2 - half, h // 2 - half, w // 2 + half, h // 2 + half),
        "ammo / HUD": (w - CROP - 40, h - CROP - 40, w - 40, h - 40),
        "abilities": (40, h - CROP - 40, CROP + 40, h - 40),
    }


def centre_pixels(image: Image.Image) -> list[tuple[int, int, int]]:
    """Flattened RGB pixels of the measurement window, where the crosshair lives."""
    w, h = image.size
    half = MEASURE // 2
    centre = image.crop((w // 2 - half, h // 2 - half, w // 2 + half, h // 2 + half)).convert("RGB")
    # Pillow types this for every mode; after convert("RGB") it is always
    # (r, g, b) triples, which mypy cannot see.
    return cast(list[tuple[int, int, int]], list(centre.get_flattened_data()))


def crosshair_mask(reference: Image.Image) -> list[int]:
    """Indices of the crosshair's pixels, taken from the lossless original.

    Two things make this measurement trustworthy, and both were learned the
    hard way:

    * **The mask comes from the reference and is reused verbatim.**
      Re-selecting "green enough" pixels per variant measures the wrong thing:
      compression desaturates the anti-aliased edge pixels below any threshold,
      they drop out of the sample, and the surviving bright core makes the
      *degraded* image score higher than the original it came from.
    * **Only near-pure green counts.** A permissive threshold admits foliage and
      green UI, which survive compression fine and mask the crosshair's loss.
      Valorant's default crosshair is pure (0, 255, 0), so the strict test
      isolates the stroke exactly -- on a sampled frame it selected 120 px, all
      of them the crosshair.
    """
    return [
        i
        for i, (r, g, b) in enumerate(centre_pixels(reference))
        if g > 200 and r < g * 0.4 and b < g * 0.4
    ]


def masked_green(image: Image.Image, mask: list[int]) -> float:
    """Mean green channel at the reference's crosshair coordinates.

    This is the number that exposes 4:2:0 chroma: on the default six-image
    sample the PNG reads 255, AVIF q80 4:4:4 around 252, and both 4:2:0 encodes
    -- AVIF q80 and WebP q90 -- around 222.

    Do not compare these with the figures in obsidian-import/images.py and
    PR #5 (PNG 248, AVIF 243, WebP 179 -- WebP at 72%). Those are from the
    original pilot, which measured the crosshair differently: its PNG baseline
    was 248, not 255. Here WebP lands at 87%. Same conclusion, different scale.
    """
    if not mask:
        return 0.0
    pixels = centre_pixels(image)
    return sum(pixels[i][1] for i in mask) / len(mask)


def encode(source: Image.Image, variant: Variant) -> tuple[bytes, float]:
    """Encode in memory and return the bytes plus how long it took.

    Encoding to a buffer rather than to disk keeps the measurement about the
    codec instead of the filesystem, and leaves no files to clean up.
    """
    flattened = source.convert("RGB")
    buffer = io.BytesIO()

    start = time.perf_counter()
    flattened.save(buffer, variant.fmt, **variant.params)
    elapsed = time.perf_counter() - start

    return buffer.getvalue(), elapsed


def crop_data_uri(image: Image.Image, box: tuple[int, int, int, int]) -> str:
    """A crop as an inline lossless PNG.

    Lossless is not optional: re-encoding these crops with anything lossy would
    add artifacts on top of the artifacts being compared, which is the one
    mistake that would invalidate the whole page.
    """
    buffer = io.BytesIO()
    image.crop(box).convert("RGB").save(buffer, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


# A plus-shaped crosshair measures around 120 px at 4K. Below this the frame
# either has no green crosshair or shows a bare dot, neither of which can
# demonstrate chroma loss on a thin stroke.
MIN_CROSSHAIR_PIXELS = 60


def select_images(source: Path, count: int, explicit: str | None) -> list[Path]:
    """Which originals to test.

    Ordered by file size, because PNG size tracks scene complexity: the biggest
    captures are the busiest frames and the worst case for every codec. But size
    alone is not enough -- a frame whose crosshair is a small dot cannot show
    chroma desaturation at all, so the page would quietly fail to demonstrate
    the thing it exists to test. Candidates are therefore skipped unless the
    original actually contains a green crosshair.

    The scan runs down the size order until `count` images qualify or the corpus
    runs out, and says so when it comes up short: a sample smaller than the one
    asked for must not pass for the one asked for.
    """
    if explicit:
        names = [name.strip() for name in explicit.split(",") if name.strip()]
        chosen = []
        for name in names:
            path = source / name
            if not path.is_file():
                raise SystemExit(f"No such image: {path}")
            chosen.append(path)
        return chosen

    pngs = sorted(source.glob("*.png"), key=lambda p: p.stat().st_size, reverse=True)
    if not pngs:
        raise SystemExit(f"No PNGs found in {source}")

    chosen, skipped = [], 0
    for path in pngs:
        with Image.open(path) as handle:
            if len(crosshair_mask(handle.convert("RGB"))) >= MIN_CROSSHAIR_PIXELS:
                chosen.append(path)
            else:
                skipped += 1
        if len(chosen) == count:
            break

    if skipped:
        print(f"Skipped {skipped} candidate(s) with no green crosshair to measure.")
    if not chosen:
        raise SystemExit(f"No images with a detectable green crosshair in {source}. Pass --images explicitly.")
    if len(chosen) < count:
        print(f"Only {len(chosen)} of the {count} requested image(s) have a green crosshair to measure.")
    return chosen


def run(images: list[Path], variants: list[Variant]) -> dict[str, list[Measurement]]:
    """Encode every image at every variant, measuring as we go.

    Results are keyed by filename, which is unique within the source directory.
    The display name is not: `Pasted image X.png` and `X.png` both read as
    `X.png`, and keying on that would silently drop one of them.
    """
    results: dict[str, list[Measurement]] = {}

    for index, path in enumerate(images, start=1):
        print(f"[{index}/{len(images)}] {path.name.removeprefix(PASTE_PREFIX)}")

        with Image.open(path) as handle:
            source = handle.convert("RGB")
            regions = crop_regions(source.size)
            mask = crosshair_mask(source)
            measurements = []

            for variant in variants:
                data, elapsed = encode(source, variant)
                with Image.open(io.BytesIO(data)) as decoded:
                    decoded.load()
                    green = masked_green(decoded, mask)
                    crops = {name: crop_data_uri(decoded, box) for name, box in regions.items()}

                measurements.append(
                    Measurement(
                        variant=variant.label,
                        size_bytes=len(data),
                        encode_seconds=elapsed,
                        crosshair_green=green,
                        crops=crops,
                    )
                )
                print(
                    f"    {variant.label:<26} {len(data) / 1024 / 1024:6.2f} MiB"
                    f"  {elapsed:5.2f}s  green {green:6.1f}"
                )

            results[path.name] = measurements

    return results


def render(results: dict[str, list[Measurement]], corpus_count: int, corpus_bytes: int) -> str:
    """Build the self-contained comparison page.

    The page's one job is in-place A/B toggling: the crops sit at 100% scale in
    the same position and the variant swaps under the cursor, because a
    difference that survives a flicker test is real and one that needs two
    windows side by side usually is not.
    """
    variant_labels = [m.variant for m in next(iter(results.values()))]
    reference_label = variant_labels[0]

    # Projected corpus size assumes the sampled ratio holds. The sample is the
    # largest files, so this reads high -- stated rather than silently applied.
    sample_source = sum(1 for _ in results)
    rows = []
    for label in variant_labels:
        sizes = [m.size_bytes for ms in results.values() for m in ms if m.variant == label]
        times = [m.encode_seconds for ms in results.values() for m in ms if m.variant == label]
        greens = [m.crosshair_green for ms in results.values() for m in ms if m.variant == label]
        ref_greens = [m.crosshair_green for ms in results.values() for m in ms if m.variant == reference_label]

        mean_green = sum(greens) / len(greens) if greens else 0.0
        mean_ref = sum(ref_greens) / len(ref_greens) if ref_greens else 0.0
        pct = (mean_green / mean_ref * 100) if mean_ref else 0.0
        mean_size = sum(sizes) / len(sizes)
        projected = mean_size * corpus_count / (1024 ** 3)

        rows.append(
            f"<tr><td>{label}</td>"
            f"<td>{mean_size / 1024 / 1024:.2f} MiB</td>"
            f"<td>{sum(times) / len(times):.2f} s</td>"
            f"<td>{mean_green:.1f} <span class='pct'>({pct:.0f}%)</span></td>"
            f"<td>{projected:.2f} GiB</td></tr>"
        )

    blocks = []
    for name, measurements in results.items():
        regions = list(measurements[0].crops)
        panes = []
        for region in regions:
            frames = "".join(
                f'<img class="frame" data-variant="{m.variant}" src="{m.crops[region]}" '
                f'alt="{region} - {m.variant}" style="{"" if i == 0 else "display:none"}">'
                for i, m in enumerate(measurements)
            )
            panes.append(f'<figure class="pane"><figcaption>{region}</figcaption>{frames}</figure>')

        stats = " &middot; ".join(
            f"{m.variant.split(' (')[0]}: {m.size_bytes / 1024 / 1024:.2f} MiB / green {m.crosshair_green:.0f}"
            for m in measurements
        )
        blocks.append(
            f'<section class="shot"><h2>{name.removeprefix(PASTE_PREFIX)}</h2>'
            f'<p class="stats">{stats}</p>'
            f'<div class="panes">{"".join(panes)}</div></section>'
        )

    buttons = "".join(
        f'<button class="variant{" active" if i == 0 else ""}" data-variant="{label}">'
        f'<kbd>{i + 1}</kbd> {label}</button>'
        for i, label in enumerate(variant_labels)
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Screenshot format comparison &mdash; Mingo-Notes</title>
<style>
  :root {{ color-scheme: dark light; }}
  body {{ font: 15px/1.5 system-ui, sans-serif; margin: 0; padding: 24px 32px 80px;
         background: #14161a; color: #e6e8ec; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .sub {{ color: #9aa3af; margin: 0 0 24px; }}
  table {{ border-collapse: collapse; margin: 0 0 28px; font-variant-numeric: tabular-nums; }}
  th, td {{ padding: 6px 14px; border-bottom: 1px solid #262b33; text-align: right; }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{ color: #9aa3af; font-weight: 600; }}
  .pct {{ color: #9aa3af; }}
  .toolbar {{ position: sticky; top: 0; z-index: 10; padding: 12px 0; margin-bottom: 16px;
              background: #14161a; border-bottom: 1px solid #262b33;
              display: flex; gap: 8px; flex-wrap: wrap; }}
  button.variant {{ font: inherit; padding: 7px 13px; border-radius: 7px; cursor: pointer;
                    background: #1d2129; color: #cbd2dc; border: 1px solid #2f3742; }}
  button.variant.active {{ background: #2f6feb; border-color: #2f6feb; color: #fff; }}
  kbd {{ font: 11px ui-monospace, monospace; opacity: .65; margin-right: 4px; }}
  .shot {{ margin: 0 0 34px; }}
  h2 {{ font-size: 15px; font-weight: 600; margin: 0 0 2px; }}
  .stats {{ color: #9aa3af; font-size: 12.5px; margin: 0 0 10px;
            font-variant-numeric: tabular-nums; }}
  .panes {{ display: flex; gap: 14px; flex-wrap: wrap; }}
  .pane {{ margin: 0; }}
  figcaption {{ color: #9aa3af; font-size: 12px; margin-bottom: 5px; }}
  .frame {{ display: block; width: {CROP}px; height: {CROP}px; image-rendering: pixelated;
            border-radius: 6px; border: 1px solid #2f3742; }}
  .hint {{ color: #9aa3af; font-size: 13px; margin: 0 0 20px; }}
</style>
</head>
<body>
<h1>Screenshot format comparison</h1>
<p class="sub">{sample_source} of the largest originals from the vault &mdash;
crops shown at 100% pixel scale. Corpus projection assumes {corpus_count} images
({corpus_bytes / 1024 ** 3:.2f} GiB of PNG); the sample is the busiest frames, so
projections read high.</p>

<table>
<tr><th>Variant</th><th>Mean size</th><th>Encode</th><th>Crosshair green</th><th>Projected corpus</th></tr>
{"".join(rows)}
</table>

<p class="hint">Click a variant or press <kbd>1</kbd>&ndash;<kbd>{len(variant_labels)}</kbd>
to swap every crop in place. Differences that survive a flicker test are real;
ones that need two windows side by side usually are not.</p>

<div class="toolbar">{buttons}</div>

{"".join(blocks)}

<script>
  const show = (variant) => {{
    document.querySelectorAll('.frame').forEach((img) => {{
      img.style.display = img.dataset.variant === variant ? '' : 'none';
    }});
    document.querySelectorAll('button.variant').forEach((btn) => {{
      btn.classList.toggle('active', btn.dataset.variant === variant);
    }});
  }};
  const variants = [...document.querySelectorAll('button.variant')].map((b) => b.dataset.variant);
  document.querySelectorAll('button.variant').forEach((btn) => {{
    btn.addEventListener('click', () => show(btn.dataset.variant));
  }});
  document.addEventListener('keydown', (event) => {{
    const index = parseInt(event.key, 10) - 1;
    if (index >= 0 && index < variants.length) show(variants[index]);
  }});
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="directory of PNG originals")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (should be outside git)")
    parser.add_argument("--count", type=int, default=6, help="how many originals to sample")
    parser.add_argument("--images", help="comma-separated filenames, overriding --count")
    args = parser.parse_args()

    # The scan stops only on reaching --count, so anything below 1 would never
    # stop it short of the whole corpus.
    if args.count < 1:
        parser.error("--count must be at least 1")
    if not args.source.is_dir():
        raise SystemExit(f"Source directory not found: {args.source}")

    corpus = list(args.source.glob("*.png"))
    images = select_images(args.source, args.count, args.images)

    print(f"Source: {args.source}  ({len(corpus)} PNGs)")
    print(f"Testing {len(images)} images x {len(VARIANTS)} variants\n")

    results = run(images, VARIANTS)
    html = render(results, len(corpus), sum(p.stat().st_size for p in corpus))

    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / "compare.html"
    destination.write_text(html, encoding="utf-8")

    print(f"\nWrote {destination}  ({destination.stat().st_size / 1024 / 1024:.1f} MiB)")


if __name__ == "__main__":
    main()
