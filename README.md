# figma-foundation-watcher

Watches the FOUNDATIONS canvas of the "F2F Web_Design System 2.0" Figma file
and posts a Slack alert to `#sed-design`, tagging Teresa Romero, whenever a
design token (color, type, spacing, effect) changes.

See [`.claude/skills/figma-foundation-watch/SKILL.md`](.claude/skills/figma-foundation-watch/SKILL.md)
for how the check runs, what secrets it needs (`FIGMA_TOKEN`,
`SLACK_BOT_TOKEN`), and the setup steps still needed before it's fully live
(Teresa isn't in the Slack workspace yet, and there's no durable recurring
trigger wired up).