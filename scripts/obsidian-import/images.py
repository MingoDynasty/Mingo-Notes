"""Screenshot conversion for the import pipeline.

The vault keeps 4K PNG originals; the site serves AVIF only. Settings were chosen
by measurement in the Phase 1 pilot (see the Screenshot storage migration plan),
not by taste:

* **AVIF over WebP** — lossy WebP is always 4:2:0 chroma, which desaturates the
  thin pure-green crosshair to ~72% of the original at *every* quality. Since a
  lineup is reproduced by aiming at that crosshair, that loss is the one thing
  this site cannot afford. AVIF encodes 4:4:4, holding 98%.
* **4:4:4** — the entire reason for the format. Dropping to 4:2:0 reintroduces
  exactly the WebP problem.
* **q80** — q60 keeps the crosshair pristine but attenuates 11-15% of strong
  structural edges on high-detail frames, degrading the wall/sky landmarks also
  used to aim. q80 holds edge retention on par with WebP q90 at a smaller
  overall corpus.
* **speed 6** — measured optimum, not a compromise. Slower settings are up to
  45x more expensive and produce marginally *larger* files; faster ones cost
  real bytes.
"""
from pathlib import Path

from PIL import Image

AVIF_QUALITY = 80

# Full-resolution chroma. The crosshair is the reason this format was chosen;
# 4:2:0 would give back the WebP desaturation this migration exists to fix.
AVIF_SUBSAMPLING = "4:4:4"

# libavif speed 0 (slowest) - 10 (fastest). 6 measured smallest-per-second.
AVIF_SPEED = 6


def convert_screenshot(src: Path, dst: Path, quality: int = AVIF_QUALITY) -> None:
    """Convert one screenshot to AVIF at native resolution.

    Images are flattened to RGB: the corpus is fully opaque 4K captures, and
    lossy encoding with an alpha channel costs bytes for nothing. Paletted or
    alpha-bearing sources are composited onto black rather than rejected, so an
    unexpected input format cannot fail the whole import.
    """
    with Image.open(src) as source:
        if source.mode in ("RGBA", "LA", "P"):
            rgba = source.convert("RGBA")
            image = Image.new("RGB", rgba.size, (0, 0, 0))
            image.paste(rgba, mask=rgba.split()[-1])
        else:
            image = source.convert("RGB")

        dst.parent.mkdir(parents=True, exist_ok=True)
        image.save(
            dst,
            "AVIF",
            quality=quality,
            subsampling=AVIF_SUBSAMPLING,
            speed=AVIF_SPEED,
        )
