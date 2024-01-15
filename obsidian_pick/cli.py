from pathlib import Path
import textwrap
import os
import pickle
import subprocess
import sys

from click import Path
import typer
import obsidiantools.api as ot

from obsidian_pick.main import app, iterate_md_files, logger, quartz_content_path, resolve_path, vault_path

app = typer.Typer()

# To be serialize the recursive graph datastsructure with picle, 
# we need to increase the recursion limit
sys.setrecursionlimit(1_000_000)

@app.command()
def generate_graph():
    vault = ot.Vault("/home/johannes/writing/obsidian/main")
    print('Connecting to vault...')
    vault = vault.connect()
    print('Gathering vault...')
    vault = vault.gather()
    pickle.dump(vault, open("vault.pickle", "wb"))

def load_vault() -> ot.Vault:
    vault = pickle.load(open("vault.pickle", "rb"))
    return vault

def is_publish_file(vault, file) -> bool:
    fm = vault.get_front_matter(file)
    return fm is not None and 'publish' in fm and fm['publish'] == 'true'

def get_publish_files(vault) -> list:
    index = vault.md_file_index
    publish_files = []
    for f in index:
        if is_publish_file(vault, f):
            publish_files.append(f)
    return publish_files

def find_unpublished_wikilinks_recursively(vault: ot.Vault, f, publish_files, links_missing_for_file, visited_files):
    if f in visited_files:
        return
    if f in vault.nonexistent_notes:
        print(f'File "{f}" does not exist')
        visited_files.append(f)
        return
    for lf in set([l for l in vault.get_wikilinks(f) if l != ""]):
        visited_files.append(f)
        if lf not in publish_files:
            links_missing_for_file.append(lf)
            find_unpublished_wikilinks_recursively(vault, lf, publish_files, links_missing_for_file, visited_files)
    return links_missing_for_file

@app.command()
def print_vault():
    vault = load_vault()
    # file = Path("/home/johannes/writing/obsidian/main") / index["VAISU talk on The Science Algorithm"]

    index = vault.md_file_index
    publish = []
    for f in index:
        fm = vault.get_front_matter(f)
        if fm is not None and 'publish' in fm and fm['publish'] == 'true':
            publish.append(f)

    publish_files = get_publish_files(vault)
    for f in publish_files:
        links_missing_for_file = []
        find_unpublished_wikilinks_recursively(vault, f, publish_files, links_missing_for_file, [])
        if len(links_missing_for_file) > 0:
            print(f'"{f}" links to these, but they are not published')
            for lf in links_missing_for_file:
                print(f"- {lf}")
            print()
        
@app.command()
def create_htaccess():
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
    subprocess.run(["npx", "quartz", "build", "--concurrency", "12"], check=True, cwd='/home/johannes/projects/quartz')
    create_htaccess()


@app.command()
def deploy(first_build: bool=False):
    if first_build:
        build()
    subprocess.run(["sudo", "rsync", "-avz", "--delete", "/home/johannes/projects/quartz/public/", "/var/www/html/"], check=True)


main = app


if __name__ == "__main__":
    print_vault()


@app.command()
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