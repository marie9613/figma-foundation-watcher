#!/usr/bin/env python3
"""
Fetches the "foundation" pages of the F2F Web Design System Figma file via
the Figma REST API, fingerprints every node's semantically-relevant
properties (name, type, fills, strokes, text style/characters, effects --
deliberately NOT position/size, since layout jitter isn't a "foundation
change"), diffs that fingerprint against the last committed snapshot, and if
anything changed, posts a summary to Slack.

Note on scope: "◼︎ FOUNDATIONS" (node 5:54) is NOT a content page -- it's a
section-divider heading in Figma's flat pages list. Figma has no real page
nesting, so this design system fakes a hierarchy with a "↳" naming
convention: the seven pages actually named "↳ Colors", "↳ Typography", etc.
are the real content, and 5:54 itself will always have zero children.
FIGMA_PAGE_IDS below points at those seven pages directly. (An eighth
page, "Pictogram", sits in the same visual position but without the "↳"
prefix -- confirmed out of scope for now.)

This is the headless / unattended path: it talks to the Figma and Slack REST
APIs directly with tokens, so it works from a cron job with no live MCP
session involved. See ../SKILL.md for the interactive fallback (using the
Figma/Slack MCP tools) when tokens aren't configured.

Required environment variables:
  FIGMA_TOKEN      Figma personal access token, "File content" read scope.
  SLACK_BOT_TOKEN  Slack bot token with chat:write scope, invited to the
                   target channel.

Optional environment variables:
  FIGMA_FILE_KEY   Defaults to the F2F Web Design System 2.0 file.
  FIGMA_PAGE_IDS   Comma-separated node IDs to watch. Defaults to the seven
                   foundation pages (see above).
  SLACK_CHANNEL_ID Which channel to post to (see the TEST CONFIG note below).
  MENTION_SLACK_ID Slack user ID to @-mention on a detected change (see the
                   TEST CONFIG note below).
"""
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

FIGMA_FILE_KEY = os.environ.get("FIGMA_FILE_KEY", "4EZqcDA8pAD4CVfPR9f9Gh")
# ↳ Colors, ↳ Typography, ↳ Spatial, ↳ Grids, ↳ Effects, ↳ Image, ↳ Assets.
FIGMA_PAGE_IDS = [
    p.strip()
    for p in os.environ.get(
        "FIGMA_PAGE_IDS",
        "37:2,37:3,24109:2951,30396:77272,24123:50,24243:6889,24243:6892",
    ).split(",")
    if p.strip()
]

# --- TEST CONFIG ---
# Pointed at #testchannel / Lorenzo while this is being validated, instead of
# the real target (#sed-design, C0173PTNZTR / Teresa Romero, U015EH28ZMG).
# Switch SLACK_CHANNEL_ID and MENTION_SLACK_ID back to those once this has
# been confirmed working end to end.
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID", "C0BNJEN2W57")
# @l.paccagnini.fl / "Lorenzo Paccagnini", confirmed member of #testchannel.
MENTION_SLACK_ID = os.environ.get("MENTION_SLACK_ID", "U09HH14A076").strip()
MENTION_FALLBACK_TEXT = "Lorenzo Paccagnini"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(SCRIPT_DIR, "..", "state", "foundations-snapshot.json")

# Fields that count as a "foundation" change. Deliberately excludes geometry
# (x/y/width/height) so the watcher doesn't fire on layout nudges.
FINGERPRINT_KEYS = ("fills", "strokes", "effects", "characters", "style", "cornerRadius")


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def figma_get(path):
    token = os.environ.get("FIGMA_TOKEN")
    if not token:
        die("FIGMA_TOKEN is not set. See SKILL.md for how to generate one.")
    req = urllib.request.Request(
        f"https://api.figma.com/v1{path}",
        headers={"X-Figma-Token": token},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        die(f"Figma API {path} failed: {e.code} {e.read().decode(errors='replace')}")


def walk(node, path_names, out):
    entry = {
        "id": node.get("id"),
        "name": node.get("name"),
        "type": node.get("type"),
        "path": " / ".join(path_names + [node.get("name", "")]),
    }
    fingerprint_src = {k: node.get(k) for k in FINGERPRINT_KEYS if k in node}
    entry["hash"] = hashlib.sha256(
        json.dumps(fingerprint_src, sort_keys=True, default=str).encode()
    ).hexdigest()
    out[entry["id"]] = entry
    for child in node.get("children", []):
        walk(child, path_names + [node.get("name", "")], out)


def fetch_snapshot():
    ids_param = ",".join(FIGMA_PAGE_IDS)
    data = figma_get(f"/files/{FIGMA_FILE_KEY}/nodes?ids={ids_param}")
    returned = data.get("nodes", {})
    out = {}
    for page_id in FIGMA_PAGE_IDS:
        node_wrapper = returned.get(page_id)
        if not node_wrapper or "document" not in node_wrapper:
            die(f"Page {page_id} not found in file {FIGMA_FILE_KEY} response.")
        walk(node_wrapper["document"], [], out)
    return out


def load_previous():
    if not os.path.exists(STATE_PATH):
        return None
    with open(STATE_PATH) as f:
        return json.load(f)


def save_snapshot(snapshot):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)
        f.write("\n")


def diff_snapshots(old, new):
    old_ids, new_ids = set(old), set(new)
    added = [new[i] for i in new_ids - old_ids]
    removed = [old[i] for i in old_ids - new_ids]
    modified = [
        {"before": old[i], "after": new[i]}
        for i in old_ids & new_ids
        if old[i]["hash"] != new[i]["hash"]
    ]
    return added, removed, modified


def build_slack_message(added, removed, modified):
    mention = f"<@{MENTION_SLACK_ID}>" if MENTION_SLACK_ID else MENTION_FALLBACK_TEXT
    lines = [
        f":rotating_light: *Foundation change detected* in the F2F Web Design System 2.0 Figma file "
        f"({len(added)} added, {len(removed)} removed, {len(modified)} modified)",
        f"cc {mention}",
        "",
    ]
    for item in modified[:15]:
        lines.append(f"• ✏️ modified: *{item['after']['path']}* ({item['after']['type']})")
    for item in added[:15]:
        lines.append(f"• ➕ added: *{item['path']}* ({item['type']})")
    for item in removed[:15]:
        lines.append(f"• ➖ removed: *{item['path']}* ({item['type']})")
    overflow = (len(added) + len(removed) + len(modified)) - 15
    if overflow > 0:
        lines.append(f"…and {overflow} more.")
    lines.append("")
    lines.append(
        "<https://www.figma.com/design/4EZqcDA8pAD4CVfPR9f9Gh/|Open the F2F Web Design System 2.0 file>"
    )
    return "\n".join(lines)


def post_to_slack(text):
    """Posts directly via the Slack REST API. Only used when SLACK_BOT_TOKEN is
    set (standalone/headless runs). When called from a Claude Code session
    that already has the Slack MCP connector, skip this and have Claude post
    with mcp__Slack__slack_send_message instead -- see main()'s else branch."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    body = json.dumps({"channel": SLACK_CHANNEL_ID, "text": text}).encode()
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.load(resp)
    if not result.get("ok"):
        die(f"Slack chat.postMessage failed: {result}")
    return result


def git_commit_state(message):
    repo_dir = os.path.join(SCRIPT_DIR, "..", "..", "..", "..")
    subprocess.run(["git", "add", STATE_PATH], cwd=repo_dir, check=True)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo_dir)
    if diff.returncode == 0:
        return False
    subprocess.run(["git", "commit", "-m", message], cwd=repo_dir, check=True)
    return True


def main():
    new_snapshot = fetch_snapshot()
    old_snapshot = load_previous()

    if old_snapshot is None:
        save_snapshot(new_snapshot)
        print(f"No previous snapshot found. Saved baseline with {len(new_snapshot)} nodes.")
        return

    added, removed, modified = diff_snapshots(old_snapshot, new_snapshot)
    if not (added or removed or modified):
        print("No foundation changes detected.")
        return

    message = build_slack_message(added, removed, modified)
    save_snapshot(new_snapshot)

    if os.environ.get("SLACK_BOT_TOKEN"):
        post_to_slack(message)
        print(
            f"Foundation change detected and posted to Slack directly: "
            f"{len(added)} added, {len(removed)} removed, {len(modified)} modified."
        )
    else:
        # No SLACK_BOT_TOKEN configured: don't post ourselves. Print the
        # message so a caller with the Slack MCP connector (e.g. a Claude
        # Code routine) can post it via mcp__Slack__slack_send_message to
        # channel C0173PTNZTR instead of over the network-restricted REST API.
        print("FOUNDATION_CHANGE_DETECTED: post the following message to Slack channel "
              f"{SLACK_CHANNEL_ID} (no SLACK_BOT_TOKEN set, so it was not sent automatically):")
        print("---")
        print(message)
        print("---")


if __name__ == "__main__":
    main()
