import re

# Obsidian image embeds this tool understands, e.g.:
#   ![[Pasted image 20250518214042.png]]
#   ![[attachments/Pasted image 20250518214042.png]]
# Group "name" captures the Obsidian filename, including the "Pasted image " prefix.
SCREENSHOT_PREFIX = "Pasted image "
_EMBED_RE = re.compile(r"!\[\[(?:attachments/)?(?P<name>Pasted image [^\[\]]*\.png)\]\]")


def rewrite_screenshot_embeds(line: str) -> str:
    """Rewrite Obsidian image embeds in ``line`` into Docusaurus image tags.

    ``![[Pasted image X.png]]`` (or the ``attachments/`` form) becomes a raw
    self-closing ``<img src="/screenshots/X.png" alt="X.png" />`` tag,
    preserving any surrounding text. Lines without a recognized embed are
    returned unchanged.

    A raw ``<img>`` tag (rather than Markdown ``![](...)``) keeps Docusaurus's
    webpack from ingesting every screenshot into its asset pipeline at build
    time, which otherwise duplicates them and drives huge RAM/disk usage. The
    tag must be self-closing because Docusaurus parses ``.md`` files as MDX.
    """

    def _replace(match: re.Match) -> str:
        stripped = match.group("name").removeprefix(SCREENSHOT_PREFIX)
        return f'<img src="/screenshots/{stripped}" alt="{stripped}" />'

    return _EMBED_RE.sub(_replace, line)


def get_screenshots_used_in_markdown_file(filename) -> set[str]:
    # Screenshots referenced by the Markdown file (names keep the "Pasted image " prefix).
    screenshots_used = set()
    with open(filename, "r", encoding="utf-8") as file_handle:
        for line in file_handle:
            for match in _EMBED_RE.finditer(line):
                screenshots_used.add(match.group("name"))
    return screenshots_used
