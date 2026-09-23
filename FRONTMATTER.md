---
name: social-content
summary: Central repository root and semantic tree orchestrator for social content,
  AI agent orchestration, innovation research, topic deep-dives, and creative publishing
  workflows.
tags:
- social-content
submodules:
  local/: Documentation and resources for local.
  projects/: Documentation and resources for projects.
  reflections/: Documentation and resources for reflections.
  scripts/: Documentation and resources for scripts. Folder/frontmatter routing hooks
    (folder_selector, folder_injector_hook, frontmatter_guard_hook, sync/lint_readme_tree)
    live in .agents/hooks/ instead, since .agents is excluded from the frontmatter
    tree.
  src/: Documentation and resources for src.
  topics/: Documentation and resources for topics.
---

# Repository Semantic Routing Tree Root

This file serves as the root manifest for TypeSafe Jev semantic directory navigation across the repository.
