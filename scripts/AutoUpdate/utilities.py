def get_screenshots_used_in_markdown_file(filename) -> set():
    # Screenshots from the Markdown files
    screenshots_used = set()
    with open(filename, "r") as file_handle:
        for line in file_handle:
            line = line.strip()
            if line.endswith('.png]]'):
                if line.startswith('![[attachments/Pasted image '):
                    filename = line.split('/')[-1][:-2]
                    screenshots_used.add(filename)
                if line.startswith('![[Pasted image '):
                    filename = line[3:-2]
                    screenshots_used.add(filename)
    return screenshots_used
