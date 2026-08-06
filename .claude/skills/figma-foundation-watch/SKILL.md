---
name: figma-foundation-watch
description: Checks the FOUNDATIONS page of Marie's "F2F Web_Design System 2.0" Figma file for changes (colors, type styles, spacing, effects -- anything at the design-token/foundation level, not regular screen work) and posts a Slack alert to #sed-design tagging Teresa Romero (teresa.romero@globant.com) when something changed. Use this skill whenever the user asks to "check the Figma foundations", "watch for design system token changes", "set up the Figma-to-Slack foundation notifier", wants to run/re-run the foundation check now, or asks about the automation living in the figma-foundation-watcher repo. Also consult it before setting up any recurring/cron trigger for this repo, since it documents the credentials and manual steps that automation depends on.
---

# Figma foundation watcher

Watches one specific part of one specific Figma file -- the `◼︎ FOUNDATIONS`
canvas (`node-id=5-54`) in `F2F Web_Design System 2.0`
(`fileKey=4EZqcDA8pAD4CVfPR9f9Gh`) -- and posts to the `#sed-design` Slack
channel (`C0173PTNZTR`) whenever that canvas changes, tagging
`teresa.romero@globant.com`. It intentionally ignores changes anywhere else
in the file: regular screen/component work should not spam this channel.

There are two ways to run the check. Prefer the scripted path; fall back to
the interactive path only when the required tokens aren't configured.

## Path A: scripted check (works unattended, e.g. from a cron trigger)

Run `scripts/check_foundations.py`. It:
1. Fetches the FOUNDATIONS subtree from the Figma REST API.
2. Fingerprints every node on semantically meaningful properties (fills,
   strokes, effects, text style/characters, corner radius) -- deliberately
   *not* position or size, so nudging a frame doesn't count as a change.
3. Diffs against `state/foundations-snapshot.json` (committed to this repo,
   so state survives across ephemeral cron runs).
4. If anything was added, removed, or modified, posts a summary to Slack and
   commits the new snapshot.

```bash
python3 .claude/skills/figma-foundation-watch/scripts/check_foundations.py
```

**Requires two secrets as environment variables** (not present in this repo
today -- ask the user to add them before relying on this path):

- `FIGMA_TOKEN` -- a Figma personal access token with "File content" read
  scope. Generate at figma.com → Settings → Security → Personal access
  tokens. Needs read access to the Humbleteam team's files.
- `SLACK_BOT_TOKEN` -- a Slack bot token (`xoxb-...`) with the `chat:write`
  scope, from an app installed in the `humbleteam-llc` workspace and invited
  to `#sed-design` (`/invite @your-bot-name` in that channel).

After each run where a diff was found, commit and push the updated
`state/foundations-snapshot.json` (the script stages+commits it locally;
still `git push` from the calling context) so the next run diffs against
the latest state instead of re-detecting the same change.

### Tagging Teresa

Confirmed via `slack_list_channel_members` on `#sed-design`: Teresa is a
member as `@teresa.romero.globant` ("Teresa Romero García"), user ID
`U015EH28ZMG`. That ID is the script's default for `TERESA_SLACK_ID`, so it
produces a real `<@U015EH28ZMG>` mention out of the box. Override the env
var only if her account ever changes. (Note: `slack_search_users` doesn't
reliably surface her by name or email -- use `slack_list_channel_members` on
the target channel instead if you ever need to re-verify.)

## Path B: interactive check (no tokens needed, but requires a live session)

When `FIGMA_TOKEN`/`SLACK_BOT_TOKEN` aren't available, do the check by hand
using the connected Figma and Slack MCP tools instead of the script:

1. Call `mcp__Figma__get_metadata` with `fileKey=4EZqcDA8pAD4CVfPR9f9Gh`,
   `nodeId=5:54`. **Caveat**: this Figma MCP integration mirrors Figma
   Desktop's currently-loaded state. If the FOUNDATIONS page hasn't been
   opened/scrolled in the desktop app recently, this call can return an
   empty node with no children -- ask the user to open that page in Figma
   desktop first, then retry.
2. Summarize the visible structure (children names/types) as a snapshot.
3. Compare it by eye (or with a temp JSON diff) against
   `state/foundations-snapshot.json` from the last scripted or manual run.
4. If something changed, use `mcp__Slack__slack_send_message` with
   `channel_id=C0173PTNZTR`, mentioning Teresa the same way as Path A (real
   `<@ID>` mention if her Slack ID is known, otherwise her email as text --
   and say so plainly rather than implying she was pinged).
5. Update `state/foundations-snapshot.json` by hand and commit it, so Path A
   runs later stay in sync.

## Setting up the recurring trigger

Neither path above is self-scheduling. To actually get "automation" (the
check running on its own, not just on request):

- The `CronCreate` tool schedules jobs *for this session only* -- they die
  when the session ends and auto-expire after 7 days regardless. Don't
  present that as durable automation; it's fine for a short-lived test but
  say so.
- For something durable, the user should set up a recurring scheduled task
  through Claude Code on the web's own scheduler (the mechanism used to
  fire this very session) pointed at a prompt like "run the
  figma-foundation-watch skill" against this repo/branch, on whatever
  cadence they want (e.g. every few hours on weekdays). That scheduler
  persists across sessions; `CronCreate` does not.

## Reporting results

When you run either path, always say plainly whether a Slack message was
actually sent, and whether it actually mentioned Teresa or just wrote her
email as inert text -- don't imply a ping happened if it didn't.
