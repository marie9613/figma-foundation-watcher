---
name: figma-foundation-watch
description: Checks the "foundation" pages of Marie's "F2F Web_Design System 2.0" Figma file for changes (colors, type styles, spacing, effects -- anything at the design-token/foundation level, not regular screen work) and posts a Slack alert (currently to a test channel/mention, see below, while this is being validated) when something changed. Use this skill whenever the user asks to "check the Figma foundations", "watch for design system token changes", "set up the Figma-to-Slack foundation notifier", wants to run/re-run the foundation check now, or asks about the automation living in the figma-foundation-watcher repo. Also consult it before setting up any recurring trigger/routine for this repo, since it documents the exact environment settings and connectors that automation depends on.
---

# Figma foundation watcher

Watches seven specific pages in `F2F Web_Design System 2.0`
(`fileKey=4EZqcDA8pAD4CVfPR9f9Gh`) and posts to Slack whenever any of them
change, tagging one specific person. It intentionally ignores changes
anywhere else in the file: regular screen/component work should not spam
this channel.

**Important, non-obvious scoping detail:** the page named `◼︎ FOUNDATIONS`
(`node-id=5:54` -- what the original Figma URL for this task pointed at)
is **not** a content page. Figma has no real page nesting, so this file
fakes a hierarchy using a `↳` prefix in page names: `◼︎ FOUNDATIONS` is a
section-divider heading in the flat pages list, and it will *always* have
zero children -- diffing it can never detect anything. The actual
foundation content lives in the seven sibling pages directly under that
heading:

| Page          | Node ID       |
|---------------|---------------|
| ↳ Colors      | `37:2`        |
| ↳ Typography  | `37:3`        |
| ↳ Spatial     | `24109:2951`  |
| ↳ Grids       | `30396:77272` |
| ↳ Effects     | `24123:50`    |
| ↳ Image       | `24243:6889`  |
| ↳ Assets      | `24243:6892`  |

Those seven are what `scripts/check_foundations.py` actually watches
(`FIGMA_PAGE_IDS`). An eighth page, `Pictogram`, sits in the same visual
position but without the `↳` prefix -- confirmed **out of scope** for now;
revisit if that turns out to be wrong.

**Currently pointed at a test target while this is being validated:**
`#testchannel` (`C0BNJEN2W57`), tagging Lorenzo Paccagnini (`U09HH14A076`).
The real target, once this is confirmed working end to end, is
`#sed-design` (`C0173PTNZTR`), tagging Teresa Romero (`U015EH28ZMG`) --
switch `SLACK_CHANNEL_ID` and `MENTION_SLACK_ID` in
`scripts/check_foundations.py` (and the routine's env vars, if one exists
by then) back to those two values to go live.

## Two read paths -- both actually work, for different reasons

Earlier drafts of this skill claimed the Figma MCP connector
(`mcp__Figma__get_metadata` etc.) was unreliable for unattended use,
because it kept returning an empty node for `node-id=5:54`. That diagnosis
was **wrong**: the connector was reporting the truth -- that page really
does have zero children -- and the empty result had nothing to do with a
live desktop session. Confirmed by calling `get_metadata` on `37:2`
(`↳ Colors`) instead: it returned a full, deep, real node tree with no
issue. So the MCP connector is in fact a reliable, stateless reader; the
original bug was watching the wrong node. (`get_variable_defs` is a
separate tool with its own "select a layer first" requirement -- this
skill doesn't use it.)

**Path A (`scripts/check_foundations.py`) is what's actually wired up.**
It's a plain Figma REST API call with a personal access token, run as a
script rather than through the MCP connector, because it produces clean
JSON that's easy to diff -- no XML-parsing needed. It's been run for real
against the seven pages above: first run saved a baseline of 8194 nodes,
and an immediate second run correctly reported no changes.

One environment-specific catch: this repo's cloud sessions/routines run
behind a network policy that blocks arbitrary outbound HTTPS by default,
so `api.figma.com` returns a `403` from the egress proxy until it's
explicitly allowlisted (see setup below). This has already been fixed once
for the current environment; a *new* environment or routine needs the same
one-time change.

**Path B (interactive, via the MCP connector) also works**, and is simpler
when a human is present -- see below.

## Path A: scripted check (the one to automate)

```bash
FIGMA_TOKEN=<token> python3 .claude/skills/figma-foundation-watch/scripts/check_foundations.py
```

It:
1. Fetches all seven foundation pages from the Figma REST API in one call.
2. Fingerprints every node on semantically meaningful properties (fills,
   strokes, effects, text style/characters, corner radius) -- deliberately
   *not* position or size, so nudging a frame doesn't count as a change.
3. Diffs against `state/foundations-snapshot.json` (committed to this repo,
   so state survives across ephemeral runs).
4. If nothing changed, prints that and exits -- nothing else happens.
5. If something changed: updates the snapshot, and either
   - posts directly to Slack if `SLACK_BOT_TOKEN` is set (a real Slack bot
     token, for use outside any Claude session), or
   - otherwise prints the composed Slack message prefixed with
     `FOUNDATION_CHANGE_DETECTED:` and does *not* post it itself -- the
     calling Claude Code session is expected to post that message with
     `mcp__Slack__slack_send_message` (`channel_id` = whatever
     `SLACK_CHANNEL_ID` is currently set to -- see the test-target note
     above) instead. This is the intended mode for a routine: no Slack
     token needed at all, since MCP connector traffic isn't subject to the
     network allowlist.
6. Whichever way it posts, always commit and push the updated
   `state/foundations-snapshot.json` afterward so the next run diffs
   against current state instead of re-detecting the same change.

### Setting this up as a real, unattended routine

`/schedule` doesn't work from inside a Claude Code *on the web* session
(this one included) -- routines must be created directly at
[claude.ai/code/routines](https://claude.ai/code/routines). Configure:

- **Repository**: `marie9613/figma-foundation-watcher`, default branch
  (merge this skill to `main` first, since routines clone from the default
  branch unless told otherwise).
- **Environment**: edit the environment's network access from **Trusted**
  to **Custom**, add `api.figma.com` to **Allowed domains**, and keep
  "include default list of common package managers" checked. Add
  `FIGMA_TOKEN` as an environment variable (a Figma personal access token,
  "File content: read-only" scope, from figma.com → Settings → Security →
  Personal access tokens). Do **not** add `SLACK_BOT_TOKEN` -- posting goes
  through the Slack connector instead (see above), and that connector
  already works with any network access level. Note: network access
  changes only take effect for *new* sessions started after saving, not
  ones already running.
- **Connectors**: make sure Slack is included (Figma isn't needed for this
  path, since the script bypasses the MCP connector entirely).
- **Trigger**: Schedule, whatever cadence makes sense (foundation tokens
  don't change often -- once or twice a day is plenty; the minimum
  interval is hourly).
- **Prompt**: something like:

  > Run `python3 .claude/skills/figma-foundation-watch/scripts/check_foundations.py`
  > in `marie9613/figma-foundation-watcher`, with `FIGMA_TOKEN` from the
  > environment. If its output starts with `FOUNDATION_CHANGE_DETECTED:`,
  > post the message between the `---` markers to the Slack channel the
  > script printed, using `mcp__Slack__slack_send_message`. Either way,
  > commit and push any change to `state/foundations-snapshot.json`. State
  > plainly in your summary whether anything changed and whether Slack was
  > posted.

  Don't set up this routine's schedule trigger yet -- it's still pointed at
  the test channel/mention (see above). Come back and confirm the real
  target is switched in before turning on a recurring schedule.

## Path B: interactive check (using the Figma MCP connector directly)

A valid alternative when working live in a session, no Figma token needed:

1. Call `mcp__Figma__get_metadata` once per page in the table above
   (`fileKey=4EZqcDA8pAD4CVfPR9f9Gh`, `nodeId=` one of the seven IDs). It
   returns a full XML node tree per page -- this is confirmed to work
   without any live desktop session.
2. Summarize the visible structure per page and compare against
   `state/foundations-snapshot.json` from the last Path A run (same node
   IDs, so they're directly comparable).
3. If something changed, use `mcp__Slack__slack_send_message` with the
   channel and mention currently configured (see the test-target note at
   the top of this file).
4. Update `state/foundations-snapshot.json` by hand and commit it, so Path A
   runs later stay in sync.

## Tagging the right person

Both the test target and the real target were confirmed the same way:
`mcp__Slack__slack_list_channel_members` on the target channel.
`slack_search_users` does **not** reliably surface people by name or
email -- don't rely on it, use the channel member list instead.

- Test: `@l.paccagnini.fl` ("Lorenzo Paccagnini"), user ID `U09HH14A076`,
  member of `#testchannel` (`C0BNJEN2W57`).
- Real (once switched over): `@teresa.romero.globant` ("Teresa Romero
  García"), user ID `U015EH28ZMG`, member of `#sed-design` (`C0173PTNZTR`).

`check_foundations.py` defaults `SLACK_CHANNEL_ID`/`MENTION_SLACK_ID` to the
test values above. When posting by hand via the Slack MCP tool, mention
whichever ID matches the channel you're actually posting to.

### Known Slack limitation: externally-shared channels

`#testchannel` (`C0BNJEN2W57`) is a Slack Connect (externally-shared)
channel. Slack blocks apps/bots from posting there directly --
`mcp__Slack__slack_send_message` fails with
`mcp_externally_shared_channel_restricted`. Use
`mcp__Slack__slack_send_message_draft` instead to create a draft for a
human to review and send; this is a Slack-side restriction, not fixable
from our side. **Before relying on automated posting to the real target,
confirm `#sed-design` is not also externally shared** -- if it is, the
same restriction applies there and automated posting won't work at all
(only drafts), which changes the design.

## Reporting results

Always say plainly whether a Slack message was actually sent (or only
drafted, per the limitation above), whether it's going to the test channel
or the real one, and whether it actually mentioned someone with a real
`<@ID>` or just wrote inert text -- don't imply a ping happened if it
didn't.
