---
name: figma-foundation-watch
description: Checks the FOUNDATIONS page of Marie's "F2F Web_Design System 2.0" Figma file for changes (colors, type styles, spacing, effects -- anything at the design-token/foundation level, not regular screen work) and posts a Slack alert (currently to a test channel/mention, see below, while this is being validated) when something changed. Use this skill whenever the user asks to "check the Figma foundations", "watch for design system token changes", "set up the Figma-to-Slack foundation notifier", wants to run/re-run the foundation check now, or asks about the automation living in the figma-foundation-watcher repo. Also consult it before setting up any recurring trigger/routine for this repo, since it documents the exact environment settings and connectors that automation depends on.
---

# Figma foundation watcher

Watches one specific part of one specific Figma file -- the `◼︎ FOUNDATIONS`
canvas (`node-id=5-54`) in `F2F Web_Design System 2.0`
(`fileKey=4EZqcDA8pAD4CVfPR9f9Gh`) -- and posts to Slack whenever that canvas
changes, tagging one specific person. It intentionally ignores changes
anywhere else in the file: regular screen/component work should not spam
this channel.

**Currently pointed at a test target while this is being validated:**
`#testchannel` (`C0BNJEN2W57`), tagging Lorenzo Paccagnini (`U09HH14A076`).
The real target, once this is confirmed working end to end, is
`#sed-design` (`C0173PTNZTR`), tagging Teresa Romero (`U015EH28ZMG`) --
switch `SLACK_CHANNEL_ID` and `MENTION_SLACK_ID` in
`scripts/check_foundations.py` (and the routine's env vars, if one exists
by then) back to those two values to go live.

## The two read paths, and why only one works unattended

**The Figma MCP connector (`mcp__Figma__get_metadata` etc.) is not reliable
for unattended checks.** Tested repeatedly, including after a fresh
reconnect: `get_metadata` on this exact page (`fileKey=4EZqcDA8pAD4CVfPR9f9Gh`,
`nodeId=5:54`) consistently returns an empty node with no children, and
`get_variable_defs` errors with "you need to select a layer first." This
connector appears to mirror a live, currently-open/selected Figma Desktop
state rather than doing a stateless remote read -- so a scheduled run with
nobody at the desktop app will see nothing and silently report "no
changes," which is worse than not checking at all. Only use it
interactively (Path B below), and only after confirming with the user that
the page is actually open in their Figma Desktop app.

**The Figma REST API (`scripts/check_foundations.py`, Path A) is
stateless and does work** -- it's a plain HTTPS call with a personal access
token, independent of anyone's desktop app. The catch: this repo's cloud
sessions/routines run behind a network policy that blocks arbitrary
outbound HTTPS by default, so `api.figma.com` returns a `403` from the
egress proxy until it's explicitly allowlisted (see setup below). This is
a one-time environment setting, not a per-run problem.

## Path A: scripted check (the one to automate)

```bash
FIGMA_TOKEN=<token> python3 .claude/skills/figma-foundation-watch/scripts/check_foundations.py
```

It:
1. Fetches the FOUNDATIONS subtree from the Figma REST API.
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
  already works with any network access level.
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

## Path B: interactive check (manual only, needs a live Figma Desktop session)

Only use this when someone is actively available to open the page first:

1. Ask the user to open the `◼︎ FOUNDATIONS` page in Figma Desktop (this
   file: `fileKey=4EZqcDA8pAD4CVfPR9f9Gh`, `node-id=5:54`).
2. Call `mcp__Figma__get_metadata` with that fileKey/nodeId. If it's still
   an empty node, the page isn't actually loaded/visible in the app --
   don't proceed as if that means "no changes."
3. Summarize the visible structure and compare it against
   `state/foundations-snapshot.json` from the last Path A run.
4. If something changed, use `mcp__Slack__slack_send_message` with the
   channel and mention currently configured (see the test-target note at
   the top of this file).
5. Update `state/foundations-snapshot.json` by hand and commit it, so Path A
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

## Reporting results

Always say plainly whether a Slack message was actually sent, whether it's
going to the test channel or the real one, and whether it actually
mentioned someone with a real `<@ID>` or just wrote inert text -- don't
imply a ping happened if it didn't.
