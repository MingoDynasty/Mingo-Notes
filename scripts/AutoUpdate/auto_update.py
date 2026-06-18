import fileinput
import logging  # Provides access to logging api.
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
from typing import Any, NoReturn, TypedDict, cast

from utilities import SCREENSHOT_PREFIX, get_screenshots_used_in_markdown_file, rewrite_screenshot_embeds

logger = logging.getLogger(__name__)
log_format = "%(asctime)-15s - %(levelname)s - %(message)s"
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=log_format)


class AppConfig(TypedDict):
    obsidian_screenshots_directory: str
    obsidian_markdown_dir: str
    git_screenshots_directory: str
    git_markdown_directory: str
    enable_markdown_auto_format: bool
    copy_screenshots: bool
    protected_markdown_files: list[str]


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


def default_config_path() -> Path:
    return Path(__file__).resolve().parent / "app.conf"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


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

    protected_markdown_files = config.setdefault("protected_markdown_files", [])
    if (
        not isinstance(protected_markdown_files, list)
        or not all(isinstance(filename, str) for filename in protected_markdown_files)
    ):
        exit_config_error("protected_markdown_files must be a list of file paths.")

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


def check_unused_files(
    screenshots_dir: str,
    md_dir: str,
    protected_screenshots: dict[str, set[str]],
) -> set[str]:
    # Screenshots in the screenshots directory
    screenshots_found = set()
    for screenshot in os.listdir(screenshots_dir):
        screenshots_found.add(screenshot)

    # Screenshots from the Markdown files
    screenshots_used = set()
    for file in os.listdir(md_dir):
        full_filename = os.path.join(md_dir, file)
        screenshots_used.update(get_screenshots_used_in_markdown_file(full_filename))

    unused_screenshots = set()
    for screenshot in screenshots_found:
        if screenshot in screenshots_used:
            continue
        else:
            is_protected = False
            for map_name, screenshots in protected_screenshots.items():
                if screenshot in screenshots:
                    logger.debug(
                        f"Skipping screenshot from unused detection, since it is likely used in ({map_name}): {screenshot}")
                    is_protected = True
                    break

            if not is_protected:
                logger.warning("Found an unused screenshot: {}".format(screenshot))
                unused_screenshots.add(screenshot)
    if not unused_screenshots:
        logger.info("No unused screenshots found.")
    else:
        logger.warning("Found {} unused screenshots.".format(len(unused_screenshots)))
        # sys.exit(1)
    return unused_screenshots


def line_prepender(filename, line):
    with open(filename, 'r+', encoding="utf-8") as f:
        content = f.read()
        f.seek(0, 0)
        f.write(line + '\n' + content)


def main() -> None:
    #
    # 0. Pull arguments from a config file.
    #
    config = load_config()

    logger.debug(f"Loaded config: {config}")

    #
    # 1. Check for unused screenshots. If any are found, throw warnings/errors.
    #
    protected_screenshots = {}
    for protected_markdown_file in config['protected_markdown_files']:
        if os.path.isfile(protected_markdown_file):
            map_name = os.path.splitext(os.path.basename(protected_markdown_file))[0]
            protected_screenshots[map_name] = get_screenshots_used_in_markdown_file(protected_markdown_file)
        else:
            logger.warning(f"Configured protected markdown file does not exist, skipping: {protected_markdown_file}")

    unused_screenshots = check_unused_files(
        config['obsidian_screenshots_directory'],
        config['obsidian_markdown_dir'],
        protected_screenshots,
    )

    #
    # 2. Copy screenshots from Obsidian to Git Repository
    #

    # TODO: move/organize screenshots into directories based on the map name
    if config['copy_screenshots']:
        git_screenshots_directory = assert_within_repo(config['git_screenshots_directory'])
        protected_stripped = {
            screenshot.removeprefix(SCREENSHOT_PREFIX)
            for screenshots in protected_screenshots.values()
            for screenshot in screenshots
        }

        # remove all screenshots from target directory, in case some screenshots are no longer used
        for filename in os.listdir(git_screenshots_directory):
            file_path = git_screenshots_directory / filename
            if os.path.isfile(file_path) and filename.endswith('.png'):

                # protect these screenshots for now
                if filename in protected_stripped:
                    logger.debug(f"Protecting screenshot from deletion: {filename}")
                else:
                    # print("Removing file: {}".format(file_path))
                    os.remove(file_path)

        screenshots_in_repo = set()
        for screenshot in os.listdir(git_screenshots_directory):
            screenshots_in_repo.add(screenshot)

        num_screenshots_copied = 0
        for screenshot in os.listdir(config['obsidian_screenshots_directory']):
            original_screenshot = screenshot
            if original_screenshot in unused_screenshots:
                logger.warning("Skipping unused screenshot: {}".format(screenshot))
                continue

            screenshot = screenshot.removeprefix(SCREENSHOT_PREFIX)
            if screenshot not in screenshots_in_repo:
                src_file = os.path.join(config['obsidian_screenshots_directory'], original_screenshot)
                dst_screenshot_file = git_screenshots_directory / screenshot
                shutil.copy(src_file, dst_screenshot_file)
                num_screenshots_copied += 1
        logger.info("Copied {} screenshots.".format(num_screenshots_copied))

    #
    # 3. Copy markdown files from Obsidian to Git Repository
    #
    num_markdowns_copied = 0
    for file in os.listdir(config['obsidian_markdown_dir']):
        full_filename = os.path.join(config['obsidian_markdown_dir'], file)
        dst_file = os.path.join(config['git_markdown_directory'], file)

        todo_markdowns = [
            'Placeholder.md'
        ]

        if file in todo_markdowns:
            logger.debug(f"Skipping Markdown file {file}.")
            continue

        logger.debug("Copying markdown file: {}".format(file))
        shutil.copy(full_filename, dst_file)
        num_markdowns_copied += 1

        # Rewrite Obsidian image embeds into Docusaurus links (operates on the repo copy).
        for line in fileinput.input(dst_file, inplace=True, encoding="utf-8"):
            print(rewrite_screenshot_embeds(line.rstrip()))

        content = f"""---
tags: ["valorant"]
---
"""
        line_prepender(dst_file, content)

        # Format the repo copy last, so Prettier sees the final content (links +
        # frontmatter). Never format the Obsidian source vault.
        if config['enable_markdown_auto_format']:
            logger.debug("Formatting markdown file: {}".format(file))
            try:
                result = subprocess.run(["npx.cmd", "prettier", dst_file, "--write"], check=False)
            except FileNotFoundError:
                logger.warning("Could not run Prettier: 'npx.cmd' not found on PATH.")
            else:
                if result.returncode != 0:
                    logger.warning(f"Prettier exited with code {result.returncode} for {dst_file}")
    logger.info("Copied {} markdown files.".format(num_markdowns_copied))


if __name__ == "__main__":
    main()
