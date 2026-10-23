# Retrieval recipes

| Situation | First move | Then |
|---|---|---|
| Find a feature implementation | `select.py "<feature>" --mode edit` | Search the selected pack for the route, class, or command name |
| Trace an error message | `select.py "<exact error>" --mode any` | Grep for the literal message, then read the stack frames only |
| Understand the repository | Read `local/repomix/index.md` | Open the largest domain that matches the task, not the whole pack |
| Update documentation | `select.py "<topic>" --mode read` | Grep headings and links, then read the matching section |
| Review a remote project | `repomix --remote owner/repo --compress --style json` | Build the manifest, then select a group |
| Navigate a monorepo | Read the domain table | Use per-domain packs and structure-only patterns for vendor code |
| Find recent intent | `repomix --include-diffs --include-logs -o local/repomix/recent.xml` | Grep commit messages, then read changed files |
| Check a change before edit | `select.py "<file or symbol>" --mode edit` | Read the group slice, edit, rerun focused tests |

## Escalation ladder

| Level | Width | Use when |
|---|---|---|
| 1 | One file block | The path and symbol are already known |
| 2 | One group pack | The feature spans a few files |
| 3 | Domain pack | The group boundary is unclear |
| 4 | Compressed repository | Architecture or cross-cutting audit |
| 5 | Full pack | Last resort; stream or grep, never paste |

## Prompt skeleton

| Slot | Value |
|---|---|
| Goal | What must change or be answered |
| Group | ID from `select.py` |
| Evidence | Files and lines already read |
| Constraint | Token budget and files not to touch |
| Output | Patch, answer, or test plan |

```text
index.md -> select.py -> group pack -> search_pack -> slice -> act -> verify
```
