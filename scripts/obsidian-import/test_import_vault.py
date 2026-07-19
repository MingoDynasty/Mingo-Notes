"""Tests for the Obsidian -> Docusaurus import.

Focus is the AVIF migration's failure modes: the embed rewriting the site depends
on, and the preflight checks that must fire *before* the importer mutates the repo.
"""
import os
from pathlib import Path

import pytest
from PIL import Image

from images import convert_screenshot
from import_vault import (
    PreflightError,
    build_source_index,
    derive_required_images,
    preflight,
    remove_stale_images,
    swap_documents,
    validate_both_directions,
)
from utilities import (
    get_screenshot_srcs_in_text,
    rewrite_screenshot_embeds,
    screenshot_output_name,
    strip_img_tags,
)


# --------------------------------------------------------------------------
# embed -> AVIF HTML rewriting
# --------------------------------------------------------------------------


def test_rewrites_embed_to_avif_img_tag():
    assert rewrite_screenshot_embeds("![[Pasted image 20250518214042.png]]") == (
        '<img src="/screenshots/20250518214042.avif" '
        'alt="20250518214042.avif" loading="lazy" />'
    )


def test_rewrites_attachments_prefixed_embed():
    assert rewrite_screenshot_embeds("![[attachments/Pasted image 20250518214042.png]]") == (
        '<img src="/screenshots/20250518214042.avif" '
        'alt="20250518214042.avif" loading="lazy" />'
    )


def test_emits_lazy_loading():
    # Independently rescues the heavy pages; the worst embeds 103 screenshots.
    assert 'loading="lazy"' in rewrite_screenshot_embeds("![[Pasted image 20250518214042.png]]")


def test_img_tag_is_self_closing_for_mdx():
    # Docusaurus parses .md as MDX; a non-self-closing tag breaks the build.
    assert rewrite_screenshot_embeds("![[Pasted image 1.png]]").endswith("/>")


def test_preserves_surrounding_text_and_multiple_embeds():
    line = "before ![[Pasted image 1.png]] middle ![[Pasted image 2.png]] after"
    result = rewrite_screenshot_embeds(line)
    assert result.startswith("before ")
    assert " middle " in result
    assert result.endswith(" after")
    assert result.count("<img ") == 2


def test_leaves_unrelated_lines_untouched():
    for line in ("## Heading", "", "![[Some other file.pdf]]", "text with ![[image.png]]"):
        assert rewrite_screenshot_embeds(line) == line


# --------------------------------------------------------------------------
# name mapping
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source,expected",
    [
        ("Pasted image 20250518214042.png", "20250518214042.avif"),
        ("20250518214042.png", "20250518214042.avif"),
        ("Pasted image with spaces.png", "with spaces.avif"),
    ],
)
def test_screenshot_output_name(source, expected):
    assert screenshot_output_name(source) == expected


def test_parses_img_srcs_back_out_of_a_document():
    text = '<img src="/screenshots/a.avif" alt="a.avif" loading="lazy" />\ntext\n'
    assert get_screenshot_srcs_in_text(text) == {"a.avif"}


def test_strip_img_tags_leaves_prose():
    text = 'intro\n<img src="/screenshots/a.avif" alt="a.avif" loading="lazy" />\noutro\n'
    assert strip_img_tags(text) == "intro\n\noutro\n"


# --------------------------------------------------------------------------
# the three preflight failures -- each must fire before any mutation
# --------------------------------------------------------------------------


def _touch(directory: Path, *names: str) -> None:
    for name in names:
        (directory / name).write_bytes(b"")


def test_preflight_fails_on_missing_source(tmp_path):
    _touch(tmp_path, "Pasted image a.png")
    index = build_source_index(tmp_path)
    with pytest.raises(PreflightError, match="no vault source"):
        preflight({"a.avif", "missing.avif"}, index)


def test_preflight_fails_on_duplicate_basename(tmp_path):
    # Obsidian's paste-time dedup only covers one flat folder; reorganising
    # attachments into per-note folders makes this reachable.
    _touch(tmp_path, "Pasted image a.png", "a.png")
    with pytest.raises(PreflightError, match="Duplicate screenshot basename"):
        build_source_index(tmp_path)


@pytest.mark.skipif(
    Path("A.tmpcase").resolve() == Path("a.tmpcase").resolve() and os.name == "nt",
    reason="needs a case-sensitive filesystem to hold both spellings at once",
)
def test_preflight_fails_on_output_collision(tmp_path):
    # Git is case-sensitive and the vault syncs across devices; a Windows
    # checkout is not. Both spellings would resolve to one file on disk.
    _touch(tmp_path, "Pasted image A.png", "Pasted image a.png")
    if len(os.listdir(tmp_path)) < 2:  # case-insensitive FS collapsed them
        pytest.skip("filesystem is case-insensitive")
    with pytest.raises(PreflightError, match="differing only by case"):
        build_source_index(tmp_path)


def test_preflight_detects_case_collision_without_touching_the_filesystem(monkeypatch, tmp_path):
    # The same check, exercised where a case-insensitive filesystem cannot host
    # both spellings -- so this failure mode stays covered on Windows.
    monkeypatch.setattr(
        "import_vault.os.listdir", lambda _: ["Pasted image A.png", "Pasted image a.png"]
    )
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    with pytest.raises(PreflightError, match="differing only by case"):
        build_source_index(tmp_path)


def test_preflight_passes_on_a_clean_vault(tmp_path):
    _touch(tmp_path, "Pasted image a.png", "Pasted image b.png")
    index = build_source_index(tmp_path)
    assert set(index) == {"a.avif", "b.avif"}
    preflight({"a.avif"}, index)  # must not raise


def test_source_index_ignores_non_png(tmp_path):
    _touch(tmp_path, "Pasted image a.png", "notes.md", "thumb.avif")
    assert set(build_source_index(tmp_path)) == {"a.avif"}


# --------------------------------------------------------------------------
# required-vs-stale handling
# --------------------------------------------------------------------------


def test_required_set_combines_prospective_and_retained(tmp_path):
    prospective = tmp_path / "new.md"
    prospective.write_text('<img src="/screenshots/new.avif" />', encoding="utf-8")
    retained = tmp_path / "existing.md"
    retained.write_text('<img src="/screenshots/kept.avif" />', encoding="utf-8")

    assert derive_required_images([prospective], [retained]) == {"new.avif", "kept.avif"}


def test_required_set_includes_images_only_the_incoming_document_references(tmp_path):
    # The reason the set is derived from prospective documents: a newly added
    # screenshot is referenced only by incoming markdown, never by current docs/**.
    prospective = tmp_path / "new.md"
    prospective.write_text('<img src="/screenshots/brand-new.avif" />', encoding="utf-8")
    assert "brand-new.avif" in derive_required_images([prospective], [])


def test_remove_stale_images_keeps_required_and_drops_the_rest(tmp_path):
    _touch(tmp_path, "keep.avif", "stale.avif")
    removed = remove_stale_images({"keep.avif"}, tmp_path)
    assert removed == 1
    assert sorted(os.listdir(tmp_path)) == ["keep.avif"]


def test_swap_documents_drops_pages_the_vault_no_longer_produces(tmp_path):
    # Otherwise the page survives while its screenshots are pruned as
    # unreferenced, leaving a page of broken images that validation cannot see.
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "Kept.md").write_text("kept", encoding="utf-8")
    destination = tmp_path / "docs"
    destination.mkdir()
    (destination / "Kept.md").write_text("old", encoding="utf-8")
    (destination / "Removed.md").write_text("gone from the vault", encoding="utf-8")

    copied, dropped = swap_documents([staging / "Kept.md"], destination)

    assert (copied, dropped) == (1, 1)
    assert sorted(p.name for p in destination.glob("*.md")) == ["Kept.md"]
    assert (destination / "Kept.md").read_text(encoding="utf-8") == "kept"


def test_validate_fails_when_a_referenced_image_is_absent(tmp_path):
    with pytest.raises(PreflightError, match="missing from the repo"):
        validate_both_directions({"gone.avif"}, tmp_path)


def test_validate_fails_on_orphans_when_managing_screenshots(tmp_path):
    _touch(tmp_path, "orphan.avif")
    with pytest.raises(PreflightError, match="Unreferenced screenshots"):
        validate_both_directions(set(), tmp_path, manages_screenshots=True)


def test_validate_only_warns_about_orphans_when_not_managing_screenshots(tmp_path):
    _touch(tmp_path, "orphan.avif")
    validate_both_directions(set(), tmp_path, manages_screenshots=False)  # must not raise


# --------------------------------------------------------------------------
# conversion
# --------------------------------------------------------------------------


def test_conversion_preserves_dimensions(tmp_path):
    src = tmp_path / "src.png"
    Image.new("RGB", (3840, 2160), (10, 120, 200)).save(src)
    dst = tmp_path / "out.avif"
    convert_screenshot(src, dst)

    with Image.open(dst) as result:
        assert result.size == (3840, 2160)
        assert result.format == "AVIF"


def test_conversion_flattens_alpha_to_rgb(tmp_path):
    src = tmp_path / "src.png"
    Image.new("RGBA", (64, 64), (255, 0, 0, 128)).save(src)
    dst = tmp_path / "out.avif"
    convert_screenshot(src, dst)

    with Image.open(dst) as result:
        assert result.mode in ("RGB", "RGBX")
        assert result.size == (64, 64)


def test_conversion_handles_plain_rgb(tmp_path):
    src = tmp_path / "src.png"
    Image.new("RGB", (64, 64), (0, 255, 0)).save(src)
    dst = tmp_path / "out.avif"
    convert_screenshot(src, dst)

    with Image.open(dst) as result:
        assert result.convert("RGB").getpixel((32, 32))[1] > 200


def test_conversion_creates_missing_parent_directory(tmp_path):
    src = tmp_path / "src.png"
    Image.new("RGB", (8, 8), (1, 2, 3)).save(src)
    dst = tmp_path / "nested" / "out.avif"
    convert_screenshot(src, dst)
    assert dst.is_file()
