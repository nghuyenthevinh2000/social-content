---
name: scripts
summary: Documentation and resources for scripts. Folder/frontmatter routing hooks
  (folder_selector, folder_injector_hook, frontmatter_guard_hook, sync/lint_readme_tree)
  live in .agents/hooks/ instead, since .agents is excluded from the frontmatter tree.
tags:
- scripts
submodules:
  webapp/: Documentation and resources for scripts/webapp.
  install-skill-hook.sh: install-skill-hook.sh — one-click installer for the TypeSafe/Jev-backed
    skill-selection router hook (scripts/skill_selector.py + scripts/skill_injecto
  skill_injector_hook.py: Skill Selection Injector (PreInvocation), backed by TypeSafe.
    Fires before the model reasons on a turn. Reads the PreInvocation payload from
    stdin, pu
  skill_selector.py: 'Skill Selection, backed by TypeSafe. Given a user''s request,
    decides which skill(s) under .agents/skills/ should be used, by asking TypeSafe
    one Noul '
---


