import fileinput
import logging  # Provides access to logging api.
import os
import shutil
import subprocess
import sys
import tomllib

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
def check_unused_files(screenshots_dir: str, md_dir: str) -> None:
    # Screenshots in the screenshots directory
    screenshots_found = set()
    for screenshot in os.listdir(screenshots_dir):
        screenshots_found.add(screenshot)

    # Screenshots from the Markdown files
    screenshots_used = set()
    for file in os.listdir(md_dir):
        full_filename = os.path.join(md_dir, file)
        with open(full_filename, "r") as file_handle:
            for line in file_handle:
                line = line.strip()
                if line.endswith('.png]]'):
                    if line.startswith('![[attachments/Pasted image '):
                        filename = line.split('/')[-1][:-2]
                        screenshots_used.add(filename)
                    if line.startswith('![[Pasted image '):
                        filename = line[3:-2]
                        screenshots_used.add(filename)

    unused_screenshots = set()
    for screenshot in screenshots_found:
        if screenshot in screenshots_used:
            continue
        else:
            logger.warning("Found an unused screenshot: {}".format(screenshot))
            unused_screenshots.add(screenshot)
    if not unused_screenshots:
        logger.info("No unused screenshots found.")
    else:
        logger.error("Found {} unused screenshots.".format(len(unused_screenshots)))
        sys.exit(1)


check_unused_files(config['obsidian_screenshots_directory'], config['obsidian_markdown_dir'])

#
# 2. Copy screenshots from Obsidian to Git Repository
#
# remove all screenshots from target directory, in case some screenshots are no longer used
for filename in os.listdir(config['git_screenshots_directory']):
    file_path = os.path.join(config['git_screenshots_directory'], filename)
    if os.path.isfile(file_path) and filename.endswith('.png'):
        os.remove(file_path)

screenshots_in_repo = set()
for screenshot in os.listdir(config['git_screenshots_directory']):
    screenshots_in_repo.add(screenshot)

num_screenshots_copied = 0
for screenshot in os.listdir(config['obsidian_screenshots_directory']):
    original_screenshot = screenshot
    screenshot = screenshot[13:]
    if screenshot not in screenshots_in_repo:
        src_file = os.path.join(config['obsidian_screenshots_directory'], original_screenshot)
        dst_file = os.path.join(config['git_screenshots_directory'], screenshot)
        shutil.copy(src_file, dst_file)
        num_screenshots_copied += 1
logger.info("Copied {} screenshots.".format(num_screenshots_copied))


def line_prepender(filename, line):
    with open(filename, 'r+') as f:
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

    logger.debug("Copying markdown file: {}".format(file))
    shutil.copy(full_filename, dst_file)
    num_markdowns_copied += 1

    if config['enable_markdown_auto_format']:
        logger.debug("Formatting markdown file: {}".format(file))
        subprocess.run(["npx", "prettier", full_filename, "--write"], shell=True, check=False)

    for line in fileinput.input(dst_file, inplace=True):
        line = line.rstrip()

        if line.endswith('.png]]'):
            if line.startswith('![[attachments/Pasted image '):
                alt_text = line.split('![[attachments/Pasted image ')[1][:-2]
                print(f"![{alt_text}](/screenshots/{alt_text})")
            if line.startswith('![[Pasted image '):
                alt_text = line.split('![[Pasted image ')[1][:-2]
                print(f"![{alt_text}](/screenshots/{alt_text})")
        else:
            print(line)
            # print('{} {}'.format(fileinput.filelineno(), line), end='') # for Python 3

    content = f"""---
tags: ["valorant"]
---
"""
    line_prepender(dst_file, content)
logger.info("Copied {} markdown files.".format(num_markdowns_copied))
