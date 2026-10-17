---
name: samples
summary: Example input files for the social content tools, such as the facebook_agent
  direct-message plan.
tags:
- samples
- facebook
- messaging
submodules:
  groups.json: Example list of group names to also share a facebook_agent post to.
  leads.json: Example facebook_agent message plan with one custom message per recipient.
---

# Samples

Example input files for the tools in this repository.

## `leads.json`

A sample [`facebook_agent`](../facebook_agent/) direct-message plan. It is a
top-level JSON array where each entry has a Facebook profile `url` and a custom
`message`, with an optional `label` used only for reporting.

The links, names, and messages are **placeholders** — replace them with real
recipients before running anything. Nothing here sends on its own; you must
invoke the command explicitly:

```bash
uv run python -m tools.facebook_agent message --plan tools/samples/leads.json
```

## `groups.json`

A sample list of group names for the [`facebook_agent`](../facebook_agent/) `post`
command's `--groups-file` flag, which also shares the post to those groups. Names
must match the group picker's exact first line and there is a limit of 9.

```bash
uv run python -m tools.facebook_agent post --text "Approved caption" \
  --groups-file tools/samples/groups.json
```

See the [`facebook_agent` README](../facebook_agent/README.md) for the plan and
group schemas, pacing flags, and exit codes. All samples use placeholder values.
