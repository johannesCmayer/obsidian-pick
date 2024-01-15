from pathlib import Path
import shutil
import textwrap
import subprocess
import uuid

from click import Path
import typer
import yaml

from obsidian_pick.obsidian import app, iterate_md_files, logger, quartz_content_path, resolve_path, vault_path

app = typer.Typer()

        
@app.command()
def create_htaccess():
    """Create a .htaccess file for the website. in the public folder (you need to build first)"""
    htaccess = """
        AuthType Basic
        AuthName "Restricted Content"
        AuthUserFile /etc/apache2/.htpasswd
        Require valid-user

        RewriteEngine On

        # Redirect old links to new links from renames
        RewriteRule "^.*2024-01-11---Maren$"  "/logs/2024-01-11---Maren---What-Makes-a-Team-Work-Well-q" [R]

        # Check if the .html version of the requested URI exists
        RewriteCond %{REQUEST_FILENAME}.html -f
        # Rewrite requests to the .html version
        RewriteRule ^(.+)$ $1.html [L]
        """
    htaccess = textwrap.dedent(htaccess).strip()
    with open('/home/johannes/projects/quartz/public/.htaccess', 'w') as f:
        f.write(htaccess)


@app.command()
def build():
    """Build the website with quartz."""
    subprocess.run(["npx", "quartz", "build", "--concurrency", "12"], check=True, cwd='/home/johannes/projects/quartz')
    create_htaccess()


@app.command()
def deploy(first_build: bool=False):
    """Copy the build websit to the server."""
    if first_build:
        build()
    subprocess.run(["sudo", "rsync", "-avz", "--delete", "/home/johannes/projects/quartz/public/", "/var/www/html/"], check=True)


def copy_to_quartz():
    """Take all the files that are tagged with `publish: true` and copy them to the quartz content folder."""
    shutil.rmtree(quartz_content_path, ignore_errors=True)
    for f in iterate_md_files():
        if not f.publish:
            continue
        relative_file_path = f.path.relative_to(vault_path)
        target_path = quartz_content_path / relative_file_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Copying {f}")
        f.save(target_path)


@app.command()
def update_quartz():
    copy_to_quartz()


@app.command()
def publish(path: Path):
    path = resolve_path(path)
    if path.is_dir():
        print(f"Warning, you provided a directory. We will publish all files in {path}.")
        for f in iterate_md_files(path):
            print(f)
        if input("OK? y/n: ") != "y":
            return
    for f in iterate_md_files(path):
        if f.publish:
            continue
        print(f"Publishing {f}")
        f.publish = True
        f.save()


@app.command()
def add_permalinks():
    """
    Add permalink and id fields to all files that do not have them yet.
    """
    for f in iterate_md_files():
        if f.frontmatter and "permalink" in f.frontmatter and "id" in f.frontmatter:
            continue
        if f.frontmatter and "id" in f.frontmatter:
            f.frontmatter["permalink"] = f.frontmatter["id"]
        elif f.frontmatter and "permalink" in f.frontmatter:
            f.frontmatter["id"] = f.frontmatter["permalink"]
        else:
            id = uuid.uuid4()
            if f.frontmatter is None:
                f.frontmatter = {}
            f.frontmatter["id"] = str(id)
            f.frontmatter["permalink"] = str(id)
        f.open("w").write(f"---\n" f"{yaml.dump(f.frontmatter)}\n" f"---\n" f"{f.text}")


@app.command()
def list_publish_tagged():
    """
    List all files that are tagged with `publish: true` in their frontmatter.
    """
    for f in iterate_md_files():
        if f.publish:
            print(f)


@app.command()
def list_vault_files():
    """List all files in the vault."""
    for f in sorted(iterate_md_files()):
        print(f)


@app.command()
def extract_frontmatter_urls():
    """Extract urls in the frontmatter of all files into the text of the file."""
    for f in iterate_md_files("references"):
        next_outer_itter = False
        for line in f.text.split("\n"):
            if "#python_obsidian/url_extraction" in line:
                logger.debug(f"Already found data therefore skipping: {line}")
                next_outer_itter = True
                break
        if next_outer_itter:
            continue

        if not f.has_url():
            logger.warning(f"Could not find a url in for file {f}")
            continue
        first_url = f.get_first_url()

        name = None
        if "page-title" in f.frontmatter:
            name = f.frontmatter["page-title"]
        else:
            name = f.name
        f.text = f"#python_obsidian/url_extraction [{name}]({first_url})\n" + f.text
        f.save()


@app.command()
def validate_references():
    for f in iterate_md_files("references"):
        if (
            not f.frontmatter
            or "page-title" not in f.frontmatter
            or "url" not in f.frontmatter
        ):
            print(f"Invalid frontmatter in {f}:")
            print(f.frontmatter)


@app.command()
def validate_files():
    validate_references()
    for f in iterate_md_files():
        assert f.frontmatter is not None, f"Invalid frontmatter in {f}"
        assert "id" in f.frontmatter
        assert "permalink" in f.frontmatter
        assert (
            f.frontmatter["id"] == f.frontmatter["permalink"]
        ), f"ID and permalink do not match in {f}"


main = app

if __name__ == "__main__":
    app()