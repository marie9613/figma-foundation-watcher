#!/usr/bin/env python3
"""Check the Foundations sub-pages of the F2F Figma file for changes.

Fetches each sub-page via the Figma REST API, hashes its normalized
structural content, and compares against state.json. Prints one line
per sub-page: "<name> unchanged|changed|baseline" plus a final
summary line "RESULT: first_run|no_changes|changed:<name>,<name>,..."

Requires FIGMA_TOKEN in the environment.
"""
import hashlib
import json
import os
import sys
import urllib.request

FILE_KEY = "4EZqcDA8pAD4CVfPR9f9Gh"
STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "state.json")

PAGES = {
    "Colors": "37:2",
    "Typography": "37:3",
    "Spatial": "24109:2951",
    "Grids": "30396:77272",
    "Effects": "24123:50",
    "Image": "24243:6889",
    "Assets": "24243:6892",
}

# Top-level fields on the /nodes response that are file-global or
# volatile (cache-busting) rather than specific to the page's content.
VOLATILE_TOP_LEVEL_KEYS = {
    "name",  # this is the FILE name, not the page name
    "lastModified",
    "thumbnailUrl",
    "version",
    "role",
    "editorType",
    "linkAccess",
}


def fetch_node(token, node_id):
    url = f"https://api.figma.com/v1/files/{FILE_KEY}/nodes?ids={node_id}"
    req = urllib.request.Request(url, headers={"X-Figma-Token": token})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def normalized_hash(payload, node_id):
    node = payload["nodes"][node_id]
    relevant = {
        "document": node.get("document"),
        "components": node.get("components", {}),
        "componentSets": node.get("componentSets", {}),
        "styles": node.get("styles", {}),
    }
    blob = json.dumps(relevant, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_state():
    if not os.path.exists(STATE_PATH):
        return None
    with open(STATE_PATH) as f:
        return json.load(f)


def main():
    token = os.environ.get("FIGMA_TOKEN")
    if not token:
        print("ERROR: FIGMA_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    prior_state = load_state()
    first_run = prior_state is None
    prior = prior_state or {name: None for name in PAGES}

    new_state = {}
    changed = []

    for name, node_id in PAGES.items():
        payload = fetch_node(token, node_id)
        h = normalized_hash(payload, node_id)
        new_state[name] = h
        if not first_run and prior.get(name) != h:
            changed.append(name)
        status = "baseline" if first_run else ("changed" if name in changed else "unchanged")
        print(f"{name} {status}")

    with open(STATE_PATH, "w") as f:
        json.dump(new_state, f, indent=2, sort_keys=True)
        f.write("\n")

    if first_run:
        print("RESULT: first_run")
    elif changed:
        print("RESULT: changed:" + ",".join(changed))
    else:
        print("RESULT: no_changes")


if __name__ == "__main__":
    main()
