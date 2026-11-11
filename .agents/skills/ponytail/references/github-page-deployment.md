# GitHub Pages Deployment & Subpath Traps (The Ponytail Way)

```text
Localhost: http://localhost:5173/slides/... (Works at domain root)
GitHub Pages: https://<user>.github.io/slides/... (404 Not Found)
Fix: ../slides/... -> https://<user>.github.io/<repo>/slides/... (200 OK)
```

## Traps & Lazy Senior Fixes

| Trap | Root Cause & Failure Mode | The Lazy Senior Fix |
|---|---|---|
| **Root-Absolute Path 404** | Hardcoding `/slides/...` or `/assets/...` in iframes, links, or image tags. When deployed to a project repository (`https://<user>.github.io/<repo>/`), leading slashes resolve against domain root, stripping `<repo>/` and returning 404. | Use relative paths (`../slides/...` or `./assets/...`) in markdown and HTML. Relative paths resolve identically on root domains and subpath sites. |
| **VitePress Base Mismatch** | Omitting repository base in `config.mts`. Static assets inside `public/` get deployed to subpath but links point to root domain. | Set `base: process.env.BASE_URL \|\| (process.env.GITHUB_ACTIONS ? '/<repo>/' : '/')` in `config.mts`. |
| **Iframe Embedding Failure** | Embedding standalone HTML tools or slides via `<iframe src="/tool/index.html">`. Fails on GitHub Pages subpaths. | Use relative directory traversal: `<iframe src="../tool/index.html">`. |
| **Hardcoded Button Links** | Buttons inside sub-pages pointing to `/slides/deck/index.html` instead of current page context. | Use `./index.html` or relative target paths to stay within current directory. |

## Path Resolution Comparison Matrix

| Environment | Base Path | Absolute Path (`/slides/index.html`) | Relative Path (`../slides/index.html`) | Status |
|---|---|---|---|---|
| **Localhost Dev** | `/` | `http://localhost:5173/slides/index.html` | `http://localhost:5173/slides/index.html` | 200 OK |
| **GitHub Pages** | `/<repo>/` | `https://<user>.github.io/slides/index.html` | `https://<user>.github.io/<repo>/slides/index.html` | Fixed (200 OK) |
| **Custom Domain** | `/` | `https://custom.com/slides/index.html` | `https://custom.com/slides/index.html` | 200 OK |

## Deployment Verification Protocol

| Step | Action | Verification Check |
|---|---|---|
| 1. Audit Links | Search repository for hardcoded root paths: `grep -rn 'src="/' \| grep -rn 'href="/'`. | Ensure assets use relative paths or framework base helpers. |
| 2. Base Setting | Verify `base` in Vite/VitePress/Astro configuration. | Must match exact GitHub repository name with leading and trailing slashes. |
| 3. Remote Check | Query deployed asset via curl: `curl -sI https://<user>.github.io/<repo>/slides/index.html`. | Must return `HTTP/2 200` without redirect loops or 404 errors. |
