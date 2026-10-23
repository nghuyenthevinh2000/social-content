# Repomix CLI reference

| Resource | Link |
|---|---|
| Official repository | https://github.com/yamadashy/repomix |
| Configuration docs | https://repomix.com/guide/configuration |
| CLI docs | https://repomix.com/guide/command-line-options |
| MCP docs | https://repomix.com/guide/mcp-server |
| Output formats | https://repomix.com/guide/output |
| Code compression | https://repomix.com/guide/code-compress |

## Selection and output

| Goal | Flag | Notes |
|---|---|---|
| Pack only paths | `--include "src/**,docs/**"` | Comma-separated globs |
| Exclude paths | `--ignore "dist/**,*.log"` | Adds to ignore rules |
| Pack exact files | `--stdin` | One path per line from stdin |
| Metadata only | `--no-files` | Structure and summary, no contents |
| Compress code | `--compress` | Tree-sitter signatures; usually 50-80% smaller |
| Per-file levels | `output.patterns` | Full, compressed, or structure-only |
| Split large output | `--split-output 2mb` | Groups by top-level directory; no file split |
| Guard context | `--token-budget 40000` | Writes output, exits non-zero on overflow |
| JSON shape | `--style json` | `files` map is easy to slice |
| Stable order | `--no-git-sort-by-changes` | Avoid churn between runs |
| Remote repo | `--remote owner/repo` | Optional `--remote-branch` |
| Full tree with include | `--include-full-directory-structure` | Context without full contents |
| Parse-safe XML | `--parsable-style` | Escape code that breaks XML |
| Change context | `--include-diffs --include-logs` | Add `--include-logs-count 20` |
| Exclude secrets | `--ignore "**/.env*,**/*.pem,**/*.key"` | Prevention, not just Secretlint detection |

## Config fields

| Field | Use |
|---|---|
| `output.filePath` | Point at `local/repomix/repomix-output.json` |
| `output.style` | `json` for slicing, `xml` for LLM prompts |
| `output.fileSummary` | Keep `true` for counts and top files |
| `output.directoryStructure` | Keep `true` for navigation |
| `output.files` | `false` for a map-only pack |
| `output.compress` | Global code compression |
| `output.patterns` | Ordered `{pattern, compress, directoryStructureOnly}` |
| `output.splitOutput` | Byte integer such as `2000000`; CLI also accepts `2mb` |
| `output.tokenBudget` | CI guard, not a hard truncation |
| `output.git.sortByChanges` | `false` for deterministic packs |
| `ignore.useGitignore` | `true` keeps private `local/` out |
| `ignore.customPatterns` | Add generated or vendor paths |
| `security.enableSecurityCheck` | Secretlint scan; leave on |

## MCP

| Tool | Use |
|---|---|
| `pack_codebase` | Pack a local directory once |
| `pack_remote_repository` | Pack a GitHub repo |
| `grep_repomix_output` | Regex search with context lines |
| `read_repomix_output` | Read a line range, not the whole pack |
| `file_system_read_file` | Sandbox-only file read |
| `file_system_read_directory` | Sandbox-only directory listing |

| Setup | Command |
|---|---|
| Start server | `npx -y repomix --mcp` |
| Confine paths | `npx -y repomix --mcp --sandbox /path/to/repo` |
| Register with client | Use the client's MCP config with command `npx` and args `-y repomix --mcp --sandbox` |

```text
--include/--stdin -> --compress -> --token-budget -> pack -> grep -> read range
```
