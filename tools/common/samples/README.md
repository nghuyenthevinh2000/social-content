---
name: samples
summary: Example input files for the social content tools, including the unified
  multi-platform post, a group list, and the facebook_agent direct-message plan.
tags:
- samples
- facebook
- messaging
- posting
submodules:
  groups.json: Example list of group names to also share a facebook_agent post to.
  leads.json: Example facebook_agent message plan with one custom message per recipient.
  post.json: Example unified multi-platform post with per-platform overrides and posting_groups.
---

# Samples

Example input files for the tools in this repository.

## `post.json`

A sample **unified post** for the shared [`tools.common`](../README.md) format. One
document records the caption and media once, then overrides them per platform, so
the same post can target Facebook, LinkedIn, and X/Twitter without three separate
inputs.

Validate it and print the resolved per-platform plans and commands (nothing is
posted):

```bash
uv run python -m tools.common post tools/common/samples/post.json
uv run python -m tools.common post tools/common/samples/post.json --platform facebook
```

The top-level `content` and `posting_groups` are shared defaults. Each
`platforms.<name>` block inherits them unless it overrides `text`, `images`, or
`video`; `posting_groups` is shared by Facebook and can be overridden there too.
See the [`tools.common` README](../README.md#unified-posting-format) for
the full schema. All values, handles, and asset paths are **placeholders** —
replace them before running any posting agent.

## `leads.json`

A sample [`facebook_agent`](../../facebook_agent/) direct-message plan. It is a
top-level JSON array where each entry has a Facebook profile `url` and a custom
`message`, with an optional `label` used only for reporting.

The links, names, and messages are **placeholders** — replace them with real
recipients before running anything. Nothing here sends on its own; you must
invoke the command explicitly:

```bash
uv run python -m tools.facebook_agent message --plan tools/common/samples/leads.json
```

## `groups.json`

A sample list of group names for the [`facebook_agent`](../../facebook_agent/) `post`
command's `--groups-file` flag, which also shares the post to those groups. Names
must match the group picker's exact first line and there is a limit of 9.

```bash
uv run python -m tools.facebook_agent post --text "Approved caption" \
  --groups-file tools/common/samples/groups.json
```

See the [`facebook_agent` README](../../facebook_agent/README.md) for the plan and
group schemas, pacing flags, and exit codes. All samples use placeholder values.
