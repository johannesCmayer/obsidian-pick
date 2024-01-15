import os
import pickle
import sys
import obsidiantools.api as ot

# To be serialize the recursive graph datastsructure with picle, 
# we need to increase the recursion limit
sys.setrecursionlimit(1_000_000)

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

def find_unpublished_wikilinks_recursively(vault: ot.Vault, f, publish_files, links_missing_for_file, visited_files):
    """Recursively find all wikilinks that published notes link to, but that are not published themselfs."""
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

def vault_analysis():
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