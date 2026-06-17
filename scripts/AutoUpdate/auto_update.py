import fileinput
import logging  # Provides access to logging api.
import os
import shutil
import subprocess
import sys
import tomllib

from utilities import get_screenshots_used_in_markdown_file, rewrite_screenshot_embeds

logger = logging.getLogger(__name__)
log_format = "%(asctime)-15s - %(levelname)s - %(message)s"
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=log_format)

#
# 0. Pull arguments from a config file.
#
with open("app.conf", "rb") as f:
    config = tomllib.load(f)

logger.debug(f"Loaded config: {config}")

#
# 1. Check for unused screenshots. If any are found, throw warnings/errors.
#
# corrode_wall_screenshots = get_screenshots_used_in_markdown_file(
#     "E:/Obsidian/Vaults/My Vault/Gaming/Valorant Sage Walls/Corrode.md")
# killjoy_screenshots = get_screenshots_used_in_markdown_file("E:/Obsidian/Vaults/My Vault/Gaming/Valorant KillJoy.md")
protected_screenshots = {
    "Breeze": get_screenshots_used_in_markdown_file(
        "E:/Obsidian/Vaults/My Vault/Gaming/Valorant Sage Walls/Breeze.md"),
    "Corrode": get_screenshots_used_in_markdown_file(
        "E:/Obsidian/Vaults/My Vault/Gaming/Valorant Sage Walls/Corrode.md"),
    "KillJoy": get_screenshots_used_in_markdown_file("E:/Obsidian/Vaults/My Vault/Gaming/Valorant KillJoy.md")
}


def check_unused_files(screenshots_dir: str, md_dir: str) -> set[str]:
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


unused_screenshots = check_unused_files(config['obsidian_screenshots_directory'], config['obsidian_markdown_dir'])

#
# 2. Copy screenshots from Obsidian to Git Repository
#

# TODO: move/organize screenshots into directories based on the map name
if config['copy_screenshots']:
    # remove all screenshots from target directory, in case some screenshots are no longer used
    for filename in os.listdir(config['git_screenshots_directory']):
        file_path = os.path.join(config['git_screenshots_directory'], filename)
        if os.path.isfile(file_path) and filename.endswith('.png'):

            # protect these screenshots for now
            is_protected = False
            for map_name, screenshots in protected_screenshots.items():
                if filename in screenshots:
                    logger.debug(f"Protecting {map_name} screenshot from deletion: {filename}")
                    is_protected = True
                    break

            if not is_protected:
                # print("Removing file: {}".format(file_path))
                os.remove(file_path)

    screenshots_in_repo = set()
    for screenshot in os.listdir(config['git_screenshots_directory']):
        screenshots_in_repo.add(screenshot)

    num_screenshots_copied = 0
    for screenshot in os.listdir(config['obsidian_screenshots_directory']):
        original_screenshot = screenshot
        if original_screenshot in unused_screenshots:
            logger.warning("Skipping unused screenshot: {}".format(screenshot))
            continue

        screenshot = screenshot[13:]
        if screenshot not in screenshots_in_repo:
            src_file = os.path.join(config['obsidian_screenshots_directory'], original_screenshot)
            dst_file = os.path.join(config['git_screenshots_directory'], screenshot)
            shutil.copy(src_file, dst_file)
            num_screenshots_copied += 1
    logger.info("Copied {} screenshots.".format(num_screenshots_copied))


def line_prepender(filename, line):
    with open(filename, 'r+', encoding="utf-8") as f:
        content = f.read()
        f.seek(0, 0)
        f.write(line + '\n' + content)


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
    for line in fileinput.input(dst_file, inplace=True,
                                openhook=fileinput.hook_encoded("utf-8")):
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
