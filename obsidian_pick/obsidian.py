import re
import yaml
from pathlib import Path
from typing import Tuple
import logging
from collections import namedtuple

from typer import Typer

app = Typer()

logger = logging.getLogger(__name__)

vault_path = Path("~/writing/obsidian/main").expanduser()
quartz_content_path = Path("~/projects/quartz/content").expanduser()


# TODO: Use the python frontmatter package instead of this briddle custom parser
class MDFile:
    """Represents a markdown file in the vault. Frontmatter accessible via subscription syntax."""
    def __init__(self, path: Path):
        """Load file from disk."""
        self.path, self.name, self.frontmatter, self.text = self._parse_file(path)

    def _parse_file(self, path: Path):
        """Parse file from disk."""
        with path.open() as f:
            frontmatter = ""
            frontmatter_mode = False
            text = ""
            lines = f.readlines()
            if len(lines) == 0:
                return (path, path.stem, {}, "")
            if lines[0].startswith("---"):
                lines = lines[1:]
                frontmatter_mode = True
            for line in lines:
                if line.startswith("---"):
                    frontmatter_mode = False
                    continue
                if frontmatter_mode:
                    frontmatter += line
                else:
                    text += line
        if frontmatter in ["", None]:
            frontmatter = None
        else:
            frontmatter = yaml.load(frontmatter, Loader=yaml.FullLoader)

        return (path, path.stem, frontmatter, text)

    def get_urls(self):
        urls = []
        for key, url in self.frontmatter.items():
            if re.match(r"url.*", key):
                urls.append(url)
        return urls

    def has_url(self):
        return len(self.get_urls()) > 0

    def get_first_url(self):
        """Find and return the first url in the frontmatter."""
        urls = self.get_urls()
        if len(urls) == 0:
            raise ValueError(f"File {self} does not have a url in the frontmatter.")
        return urls[0]

    def save(self, path=None):
        """Save file to disk."""
        content = ""
        if self.frontmatter:
            content += f"---\n" f"{yaml.dump(self.frontmatter)}\n" f"---\n"
        content += self.text
        path = path or self.path
        with path.open("w") as f:
            f.write(content)
   
    @property 
    def publish(self):
        """Return True if the file contains an entry `publish: true` in the frontmatter."""
        return self.frontmatter and "publish" in self.frontmatter and self.frontmatter["publish"] == "true"

    @publish.setter
    def publish(self, value):
        if self.frontmatter is None:
            self.frontmatter = {}
        self.frontmatter["publish"] = value

    def __str__(self):
        return str(self.path)

    def __getitem__(self, key):
        self.frontmatter[key]
        
    def __setitem__(self, key, value):
        self.frontmatter[key] = value


def iterate_vault_paths(rel_path: str = ""):
    path = resolve_path(rel_path)
    if not path.exists():
        raise ValueError(f"Path {path} does not exist.")
    for f in path.rglob("*"):
        if (
            not f.is_file()
            or f.suffix != ".md"
            or f.name.lower() == "readme.md"
            or ".obsidian" in str(f)
            or f.name.endswith(".excalidraw.md")
        ):
            continue
        yield f


def iterate_md_files(rel_path: str = ""):
    for f in iterate_vault_paths(rel_path):
        yield MDFile(f)

def resolve_path(path: Path):
    if not path:
        return vault_path
    elif path.is_relative_to(vault_path):
        new_path = vault_path / path
    else:
        new_path = path
    if not new_path.exists():
        raise ValueError(f"Path {path} could not be resolved. Tried {new_path}, but it does not exist.")
    return new_path


if __name__ == "__main__":
    app()
