import hashlib
import json
import logging  # Provides access to logging api.
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
from typing import Any, NoReturn, TypedDict, cast

from images import convert_screenshot, encoder_fingerprint
from utilities import (
    SCREENSHOT_PREFIX,
    get_screenshot_srcs_in_file,
    get_screenshot_srcs_in_text,
    rewrite_screenshot_embeds,
    screenshot_output_name,
)

logger = logging.getLogger(__name__)
log_format = "%(asctime)-15s - %(levelname)s - %(message)s"
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=log_format)

# Pillow logs a couple of DEBUG lines per chunk per image, which at 569 4K PNGs
# buries this script's own output entirely.
logging.getLogger("PIL").setLevel(logging.INFO)

# Vault notes that are drafts, not site pages.
SKIPPED_MARKDOWN_FILES = ("Placeholder.md",)

# What the screenshots directory is allowed to contain, and therefore what the
# stale-pruning step is allowed to delete.
IMAGE_SUFFIXES = frozenset({".avif", ".png", ".webp", ".jpg", ".jpeg", ".gif"})

# Records which vault source, at which content hash and encoder settings, produced
# each generated asset. Committed, because it has to survive a fresh checkout --
# that is precisely the case mtimes cannot answer. Kept out of static/ so it is
# not served by the site.
MANIFEST_FILENAME = "screenshot_manifest.json"

FRONTMATTER = """---
tags: ["valorant"]
---
"""


class AppConfig(TypedDict):
    obsidian_screenshots_directory: str
    obsidian_markdown_dir: str
    git_screenshots_directory: str
    git_markdown_directory: str
    enable_markdown_auto_format: bool
    copy_screenshots: bool


REQUIRED_CONFIG_KEYS = (
    "obsidian_screenshots_directory",
    "obsidian_markdown_dir",
    "git_screenshots_directory",
    "git_markdown_directory",
    "enable_markdown_auto_format",
    "copy_screenshots",
)
DIRECTORY_CONFIG_KEYS = (
    "obsidian_screenshots_directory",
    "obsidian_markdown_dir",
    "git_screenshots_directory",
    "git_markdown_directory",
)
BOOLEAN_CONFIG_KEYS = (
    "enable_markdown_auto_format",
    "copy_screenshots",
)


class PreflightError(Exception):
    """Raised when the import cannot proceed safely.

    Every check that raises this runs *before* any file is written, so a failure
    leaves the repo exactly as it was.
    """


class ValidationError(Exception):
    """Raised by the closing check, after documents are already in place.

    Distinct from PreflightError so the CLI can never claim "no changes were
    made" about a run that had in fact already swapped documents.
    """


def default_config_path() -> Path:
    return Path(__file__).resolve().parent / "app.conf"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def docs_root() -> Path:
    return repo_root() / "docs"


def exit_config_error(message: str) -> NoReturn:
    logger.error("Invalid config: %s", message)
    sys.exit(1)


def validate_config(config: dict[str, Any]) -> AppConfig:
    missing_keys = [key for key in REQUIRED_CONFIG_KEYS if key not in config]
    if missing_keys:
        exit_config_error(f"Missing required key(s): {', '.join(missing_keys)}")

    for key in DIRECTORY_CONFIG_KEYS:
        value = config[key]
        if not isinstance(value, str):
            exit_config_error(f"{key} must be a directory path string.")
        if not Path(value).is_dir():
            exit_config_error(f"{key} does not point to an existing directory: {value}")

    for key in BOOLEAN_CONFIG_KEYS:
        if not isinstance(config[key], bool):
            exit_config_error(f"{key} must be true or false.")

    return cast(AppConfig, config)


def load_config(config_path: Path | None = None) -> AppConfig:
    resolved_config_path = config_path or default_config_path()
    try:
        with open(resolved_config_path, "rb") as f:
            return validate_config(tomllib.load(f))
    except FileNotFoundError:
        exit_config_error(f"Config file not found: {resolved_config_path}")
    except tomllib.TOMLDecodeError as exc:
        exit_config_error(f"Could not parse {resolved_config_path}: {exc}")


def assert_within_repo(path: str | os.PathLike[str], root: Path | None = None) -> Path:
    resolved_root = (root or repo_root()).resolve()
    target = Path(path).resolve()
    if not target.is_relative_to(resolved_root):
        logger.error("Refusing to delete: %s is outside the repo (%s).", target, resolved_root)
        sys.exit(1)
    return target


def build_source_index(screenshots_dir: str | Path) -> dict[str, Path]:
    """Map served filename -> vault source path, failing on ambiguity.

    Two preflight failures live here because both are ambiguities in the *source*
    set, detectable before anything is written:

    * duplicate basename — two vault files reduce to the same served name (e.g.
      ``Pasted image A.png`` alongside ``A.png``). Obsidian's paste-time dedup
      only covers a single flat folder, so this becomes reachable the moment
      attachments are reorganised.
    * output collision — two sources whose outputs differ only by case
      (``A.png`` and ``a.png``). Git is case-sensitive and the vault syncs across
      devices, but the Windows checkout is not: both would resolve to one file,
      and a page would show the wrong screenshot.
    """
    screenshots_dir = Path(screenshots_dir)
    by_stripped: dict[str, list[Path]] = {}
    by_output: dict[str, Path] = {}

    for entry in sorted(os.listdir(screenshots_dir)):
        source = screenshots_dir / entry
        if not source.is_file() or not entry.lower().endswith(".png"):
            continue
        by_stripped.setdefault(entry.removeprefix(SCREENSHOT_PREFIX), []).append(source)
        by_output[screenshot_output_name(entry)] = source

    duplicates = {name: paths for name, paths in by_stripped.items() if len(paths) > 1}
    if duplicates:
        detail = "; ".join(
            f"{name} <- {', '.join(p.name for p in paths)}" for name, paths in sorted(duplicates.items())
        )
        raise PreflightError(f"Duplicate screenshot basename(s) in the vault: {detail}")

    folded: dict[str, list[str]] = {}
    for name in by_output:
        folded.setdefault(name.lower(), []).append(name)
    collisions = {key: names for key, names in folded.items() if len(names) > 1}
    if collisions:
        detail = "; ".join(f"{' vs '.join(sorted(names))}" for names in sorted(collisions.values()))
        raise PreflightError(f"Output collision(s), differing only by case: {detail}")

    return by_output


def render_document(source_path: Path) -> str:
    """Produce the site document for one vault note, without writing to the repo."""
    body = source_path.read_text(encoding="utf-8")
    rewritten = "\n".join(rewrite_screenshot_embeds(line) for line in body.splitlines())
    return FRONTMATTER + rewritten + "\n"


def format_documents(directory: Path) -> None:
    """Run Prettier over generated documents, so it sees links + frontmatter."""
    try:
        result = subprocess.run(
            ["npx.cmd", "prettier", str(directory), "--write"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        logger.warning("Could not run Prettier: 'npx.cmd' not found on PATH.")
        return
    if result.returncode != 0:
        logger.warning("Prettier exited with code %s: %s", result.returncode, result.stderr.strip())


def generate_prospective_documents(config: AppConfig, staging_dir: Path) -> list[Path]:
    """Step (a): render the incoming documents into a staging directory.

    Nothing under the repo is touched here. The required-image set has to come
    from these *prospective* documents rather than from current ``docs/**``,
    because a newly added screenshot is referenced only by incoming markdown.
    """
    generated = []
    for filename in sorted(os.listdir(config["obsidian_markdown_dir"])):
        if not filename.endswith(".md"):
            continue
        if filename in SKIPPED_MARKDOWN_FILES:
            logger.debug("Skipping Markdown file %s.", filename)
            continue
        destination = staging_dir / filename
        destination.write_text(
            render_document(Path(config["obsidian_markdown_dir"]) / filename), encoding="utf-8"
        )
        generated.append(destination)

    if config["enable_markdown_auto_format"]:
        format_documents(staging_dir)
    return generated


def collect_retained_documents(generated_dir: Path) -> list[Path]:
    """Step (b): site documents this run does not generate.

    These pages reference screenshots too (the Sage Walls pages, for instance),
    and their needs are derived here rather than from a hand-maintained
    protected-file list.
    """
    generated_dir = generated_dir.resolve()
    return [
        path
        for path in sorted(docs_root().rglob("*.md"))
        if not path.resolve().is_relative_to(generated_dir)
    ]


def derive_required_images(prospective: list[Path], retained: list[Path]) -> set[str]:
    """Step (c): the complete set of screenshots the site will reference."""
    required: set[str] = set()
    for path in prospective:
        required |= get_screenshot_srcs_in_text(path.read_text(encoding="utf-8"))
    for path in retained:
        required |= get_screenshot_srcs_in_file(path)
    return required


def preflight(required: set[str], source_index: dict[str, Path]) -> None:
    """Step (c): fail before any mutation if a required screenshot has no source."""
    missing = sorted(name for name in required if name not in source_index)
    if missing:
        preview = ", ".join(missing[:10])
        suffix = f" (and {len(missing) - 10} more)" if len(missing) > 10 else ""
        raise PreflightError(
            f"{len(missing)} referenced screenshot(s) have no vault source: {preview}{suffix}"
        )


def preflight_existing_images(required: set[str], destination_dir: Path) -> None:
    """Step (c) for runs that will not convert anything.

    With ``copy_screenshots = false`` step (d) never runs, so having a vault
    source is not enough — the image must already be in the repo. Without this,
    a newly embedded screenshot passes preflight, the documents are swapped to
    reference it, and only the closing validation notices it was never converted:
    a mutation that the ordering guarantee says cannot happen.
    """
    missing = sorted(name for name in required if not (destination_dir / name).is_file())
    if missing:
        preview = ", ".join(missing[:10])
        suffix = f" (and {len(missing) - 10} more)" if len(missing) > 10 else ""
        raise PreflightError(
            f"copy_screenshots is false, but {len(missing)} referenced screenshot(s) "
            f"are not in the repo and would not be converted: {preview}{suffix}"
        )


def source_digest(path: Path) -> str:
    """Content fingerprint of a vault source."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, dict[str, str]]:
    """Read the source fingerprint recorded for each generated asset."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        logger.warning("Manifest is unreadable (%s); every screenshot will reconvert.", exc)
        return {}
    return data if isinstance(data, dict) else {}


def save_manifest(path: Path, manifest: dict[str, dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")


def needs_conversion(
    name: str,
    source: Path,
    destination: Path,
    manifest: dict[str, dict[str, str]],
    fingerprint: str,
) -> bool:
    """Whether a required screenshot has to be (re)converted.

    Keyed on the *content* of the vault source rather than its timestamp. Git
    does not preserve mtimes, so a fresh clone or worktree stamps every asset
    with the checkout time: a source edited before that checkout would compare
    "older" than its own output and be skipped, silently serving a stale image.
    Timestamps from two independent filesystems cannot answer this question;
    only the bytes can.

    The recorded encoder fingerprint is checked too, so changing quality,
    subsampling or speed reconverts the corpus instead of leaving a silent mix
    of settings.
    """
    if not destination.exists():
        return True
    entry = manifest.get(name)
    if entry is None:
        return True
    if entry.get("encoder") != fingerprint:
        return True
    return entry.get("source_sha256") != source_digest(source)


def convert_required_images(
    required: set[str],
    source_index: dict[str, Path],
    destination_dir: Path,
    manifest: dict[str, dict[str, str]],
) -> int:
    """Step (d): every required screenshot must convert before documents move."""
    fingerprint = encoder_fingerprint()
    pending = [
        name
        for name in sorted(required)
        if needs_conversion(name, source_index[name], destination_dir / name, manifest, fingerprint)
    ]
    for index, name in enumerate(pending, 1):
        source = source_index[name]
        # Digest the source *before* handing it to the encoder. Syncthing writes
        # into this vault continuously, so the file can be replaced mid-run.
        # Hashing afterwards would certify the new bytes against an output
        # encoded from the old ones, marking a stale image current forever.
        # Recording the pre-conversion digest fails the other way: the next run
        # sees a mismatch and reconverts.
        digest = source_digest(source)
        convert_screenshot(source, destination_dir / name)
        manifest[name] = {"source_sha256": digest, "encoder": fingerprint}
        if index % 50 == 0:
            logger.info("Converted %s/%s screenshots...", index, len(pending))
    return len(pending)


def remove_stale_images(required: set[str], destination_dir: Path) -> int:
    """Step (e): drop repo screenshots nothing references any more.

    Only image files are candidates for deletion. This directory is generated
    output, but that is no reason for a destructive step to remove something it
    does not recognise, so anything else is left alone and reported.
    """
    removed = 0
    foreign = []
    for entry in sorted(os.listdir(destination_dir)):
        path = destination_dir / entry
        if not path.is_file() or entry in required:
            continue
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            foreign.append(entry)
            continue
        logger.debug("Removing stale screenshot: %s", entry)
        os.remove(path)
        removed += 1
    if foreign:
        logger.warning(
            "Left %s non-image file(s) in the screenshots directory untouched: %s",
            len(foreign),
            ", ".join(foreign[:10]),
        )
    return removed


def swap_documents(prospective: list[Path], destination_dir: Path) -> tuple[int, int]:
    """Step (e): replace the generated documents, last, once images are in place.

    Documents the vault no longer produces are deleted rather than left behind.
    A lingering one would keep referencing screenshots that this run has already
    pruned as unreferenced — a page of broken images that the reference-set
    validation, which only knows about required images, would not catch.
    """
    expected = {path.name for path in prospective}
    for path in prospective:
        shutil.copyfile(path, destination_dir / path.name)

    removed = 0
    for existing in sorted(destination_dir.glob("*.md")):
        if existing.name not in expected:
            os.remove(existing)
            removed += 1
    return len(prospective), removed


def validate_both_directions(
    required: set[str], destination_dir: Path, manages_screenshots: bool = True
) -> None:
    """Every referenced image exists on disk, and every image on disk is referenced.

    Closes the audit finding that raw ``<img>`` tags bypass Docusaurus's
    broken-link checking, so a deleted screenshot 404s silently in production.

    A missing screenshot is always an error — the site would ship a broken image.
    An orphan is only an error when this run manages the screenshot directory;
    with ``copy_screenshots = false`` the run has no mandate to prune, so it
    reports rather than fails.
    """
    on_disk = {
        entry
        for entry in os.listdir(destination_dir)
        if (destination_dir / entry).is_file()
        and Path(entry).suffix.lower() in IMAGE_SUFFIXES
    }
    missing = sorted(required - on_disk)
    if missing:
        raise ValidationError(
            f"Referenced screenshots missing from the repo: {', '.join(missing[:10])}"
        )
    orphaned = sorted(on_disk - required)
    if orphaned:
        if manages_screenshots:
            raise ValidationError(
                f"Unreferenced screenshots left in the repo: {', '.join(orphaned[:10])}"
            )
        logger.warning("%s unreferenced screenshot(s) in the repo.", len(orphaned))


def main() -> None:
    config = load_config()
    logger.debug("Loaded config: %s", config)

    git_screenshots_directory = assert_within_repo(config["git_screenshots_directory"])
    git_markdown_directory = assert_within_repo(config["git_markdown_directory"])

    with tempfile.TemporaryDirectory(prefix="obsidian-import-") as staging:
        staging_dir = Path(staging)

        # (a) render incoming documents, (b) add the pages this run does not own
        prospective = generate_prospective_documents(config, staging_dir)
        retained = collect_retained_documents(git_markdown_directory)
        logger.info(
            "Generated %s document(s); combined with %s existing site document(s).",
            len(prospective),
            len(retained),
        )

        # (c) derive the required set and refuse to mutate anything if it is unsatisfiable
        required = derive_required_images(prospective, retained)
        source_index = build_source_index(config["obsidian_screenshots_directory"])
        preflight(required, source_index)
        logger.info(
            "%s screenshot(s) required; %s available in the vault.",
            len(required),
            len(source_index),
        )

        if config["copy_screenshots"]:
            # (d) convert everything required, before any document or asset moves
            manifest_path = Path(__file__).resolve().parent / MANIFEST_FILENAME
            manifest = load_manifest(manifest_path)
            converted = convert_required_images(
                required, source_index, git_screenshots_directory, manifest
            )
            # (e) only now: swap documents and drop what nothing references
            removed = remove_stale_images(required, git_screenshots_directory)
            for name in set(manifest) - required:
                del manifest[name]
            save_manifest(manifest_path, manifest)
            logger.info("Converted %s screenshot(s); removed %s stale file(s).", converted, removed)
            unused = len(source_index) - len(required)
            if unused:
                logger.info("%s vault attachment(s) are not referenced by the site.", unused)
        else:
            # Step (d) will not run, so the required images must already be here
            # before anything is swapped.
            preflight_existing_images(required, git_screenshots_directory)
            logger.info("copy_screenshots is false; leaving %s untouched.", git_screenshots_directory)

        copied, dropped = swap_documents(prospective, git_markdown_directory)
        logger.info("Copied %s markdown files; removed %s no longer in the vault.", copied, dropped)

    validate_both_directions(required, git_screenshots_directory, config["copy_screenshots"])
    logger.info("Validated %s screenshot reference(s) in both directions.", len(required))


if __name__ == "__main__":
    try:
        main()
    except PreflightError as exc:
        logger.error("Preflight failed, no changes were made: %s", exc)
        sys.exit(1)
    except ValidationError as exc:
        logger.error("Import ran, but the closing validation failed: %s", exc)
        sys.exit(1)
