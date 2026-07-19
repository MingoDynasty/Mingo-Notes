import re

# Obsidian image embeds this tool understands, e.g.:
#   ![[Pasted image 20250518214042.png]]
#   ![[attachments/Pasted image 20250518214042.png]]
# Group "name" captures the Obsidian filename, including the "Pasted image " prefix.
SCREENSHOT_PREFIX = "Pasted image "
_EMBED_RE = re.compile(r"!\[\[(?:attachments/)?(?P<name>Pasted image [^\[\]]*\.png)\]\]")

# Screenshots as they appear in generated//hand-written site documents.
_IMG_SRC_RE = re.compile(r'<img\s[^>]*src="/screenshots/(?P<name>[^"]+)"[^>]*>')

# Extension the repo serves. Originals stay PNG in the vault; only the repo copy
# is converted (see the Screenshot storage migration plan).
AVIF_SUFFIX = ".avif"


def screenshot_output_name(source_name: str) -> str:
    """Map a vault attachment filename to the filename served by the site.

    ``Pasted image 20250518214042.png`` -> ``20250518214042.avif``.
    """
    stripped = source_name.removeprefix(SCREENSHOT_PREFIX)
    return stripped.rsplit(".", 1)[0] + AVIF_SUFFIX


def rewrite_screenshot_embeds(line: str) -> str:
    """Rewrite Obsidian image embeds in ``line`` into Docusaurus image tags.

    ``![[Pasted image X.png]]`` (or the ``attachments/`` form) becomes a raw
    self-closing ``<img src="/screenshots/X.avif" alt="X.avif" loading="lazy" />``
    tag, preserving any surrounding text. Lines without a recognized embed are
    returned unchanged.

    A raw ``<img>`` tag (rather than Markdown ``![](...)``) keeps Docusaurus's
    webpack from ingesting every screenshot into its asset pipeline at build
    time, which otherwise duplicates them and drives huge RAM/disk usage. The
    tag must be self-closing because Docusaurus parses ``.md`` files as MDX.

    ``loading="lazy"`` matters independently of the format change: the heaviest
    page embeds 103 screenshots, and without it every one loads up front.
    """

    def _replace(match: re.Match) -> str:
        output = screenshot_output_name(match.group("name"))
        return f'<img src="/screenshots/{output}" alt="{output}" loading="lazy" />'

    return _EMBED_RE.sub(_replace, line)


def get_screenshots_used_in_markdown_file(filename) -> set[str]:
    # Screenshots referenced by the Markdown file (names keep the "Pasted image " prefix).
    screenshots_used = set()
    with open(filename, "r", encoding="utf-8") as file_handle:
        for line in file_handle:
            for match in _EMBED_RE.finditer(line):
                screenshots_used.add(match.group("name"))
    return screenshots_used


def get_screenshot_srcs_in_text(text: str) -> set[str]:
    """Screenshot filenames referenced by ``<img src="/screenshots/...">`` tags.

    Used to derive the required-image set from site documents, which — unlike the
    vault sources — already carry rewritten tags.
    """
    return {match.group("name") for match in _IMG_SRC_RE.finditer(text)}


def get_screenshot_srcs_in_file(filename) -> set[str]:
    with open(filename, "r", encoding="utf-8") as file_handle:
        return get_screenshot_srcs_in_text(file_handle.read())


def strip_img_tags(text: str) -> str:
    """Remove ``<img>`` tags so two documents can be compared on prose alone.

    Backs the migration's content-drift assertion: the format switch must rewrite
    image tags and change nothing else.
    """
    return _IMG_SRC_RE.sub("", text)
