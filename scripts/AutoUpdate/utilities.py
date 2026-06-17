import re

# Obsidian image embeds this tool understands, e.g.:
#   ![[Pasted image 20250518214042.png]]
#   ![[attachments/Pasted image 20250518214042.png]]
# Group "name" captures the Obsidian filename, including the "Pasted image " prefix.
SCREENSHOT_PREFIX = "Pasted image "
_EMBED_RE = re.compile(r"!\[\[(?:attachments/)?(?P<name>Pasted image [^\[\]]*\.png)\]\]")


def rewrite_screenshot_embeds(line: str) -> str:
    """Rewrite Obsidian image embeds in ``line`` into Docusaurus image links.

    ``![[Pasted image X.png]]`` (or the ``attachments/`` form) becomes
    ``![X.png](/screenshots/X.png)``, preserving any surrounding text. Lines
    without a recognized embed are returned unchanged.
    """

    def _replace(match: re.Match) -> str:
        stripped = match.group("name").removeprefix(SCREENSHOT_PREFIX)
        return f"![{stripped}](/screenshots/{stripped})"

    return _EMBED_RE.sub(_replace, line)


def get_screenshots_used_in_markdown_file(filename) -> set[str]:
    # Screenshots referenced by the Markdown file (names keep the "Pasted image " prefix).
    screenshots_used = set()
    with open(filename, "r", encoding="utf-8") as file_handle:
        for line in file_handle:
            for match in _EMBED_RE.finditer(line):
                screenshots_used.add(match.group("name"))
    return screenshots_used
