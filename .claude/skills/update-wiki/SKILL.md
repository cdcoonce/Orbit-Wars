---
name: update-wiki
description: >
  Rewrites the prose sections of wiki pages in-place. Reads source files to
  understand current context, then updates only the content inside
  <!-- claude:prose --> ... <!-- claude:prose:end --> markers. Never touches
  <!-- generated:start --> ... <!-- generated:end --> blocks. Supports
  targeting a single page with /update-wiki {PageName}.
triggers:
  - /update-wiki
  - /update-wiki {PageName}
---

# Update Wiki Skill

Refresh the hand-written prose sections of wiki pages to reflect the current
state of the codebase. Generated metric/data blocks are managed by the
orchestrator and must never be touched.

## When to Invoke

- User types `/update-wiki` — update all prose-bearing pages
- User types `/update-wiki Architecture` — update only `wiki/Architecture.md`
- User says "refresh wiki prose", "update onboarding narrative", "rewrite architecture docs"
- After a significant refactor that changes the system design narrative

## What This Skill Does (Step by Step)

1. **Determine scope.** If a page name argument was provided (e.g., `Architecture`),
   resolve it to `wiki/{PageName}.md`. Otherwise queue all prose-bearing pages listed
   below.

2. **For each target page:**
   a. Read the wiki page file.
   b. Identify every `<!-- claude:prose -->` ... `<!-- claude:prose:end -->` block.
   c. Read the relevant source files listed in the page registry below to build context.
   d. Rewrite the content between the markers so it accurately reflects the current
   codebase — keep the same general structure (headings, paragraph order) unless
   it is factually wrong.
   e. Write the updated content back to the file, with the markers preserved exactly.

3. **Never touch generated blocks.** Any content inside
   `<!-- generated:start -->` ... `<!-- generated:end -->` must be left byte-for-byte
   identical. These blocks are maintained by the wiki orchestrator script.

4. **Architecture-Decision-Log is fully Claude-owned.** `wiki/Architecture-Decision-Log.md`
   has no `generated` blocks and no `claude:prose` markers. Claude maintains the entire
   file. When updating, append new ADL entries for any architectural decisions made
   since the last recorded entry. Do not modify existing entries.

5. **Commit prompt.** After all pages are updated, remind the user:
   > "Wiki prose updated. Run `/commit` to save changes, then push to the wiki remote."

## Prose-Bearing Pages and Their Source Files

### `wiki/Architecture.md`

**Prose block purpose:** System design narrative — explains module responsibilities,
data flow, and how the static site + Lambda chat agent fit together.

**Relevant source files to read:**

- `WebContent/js/main.js`
- `WebContent/js/filter.js`
- `WebContent/js/carousel.js`
- `WebContent/js/utils.js`
- `lambda/lambda_function.py`
- `index.html` (for page structure context)
- `projects.html` (for page structure context)

### `wiki/Lambda-Chat-Agent.md`

**Prose block purpose:** Agent design rationale — explains the Lambda architecture,
knowledge base loading, prompt construction, and response handling.

**Relevant source files to read:**

- `lambda/lambda_function.py`
- `lambda/context/` (all `.md` files if present)

### `wiki/Contributing.md`

**Prose block purpose:** Onboarding narrative — explains the development workflow,
testing philosophy, and project conventions for new contributors.

**Relevant source files to read:**

- `CLAUDE.md`
- `Makefile`
- `package.json`
- `pyproject.toml`
- `.github/workflows/ci-cd.yml`

### `wiki/Architecture-Decision-Log.md`

**Special handling:** No `claude:prose` markers. Claude owns the entire file.
Append new ADL entries; never modify existing ones.

**Relevant source files to read:**

- Review recent git log for significant architectural changes
- `CLAUDE.md` for current tooling decisions
- `lambda/lambda_function.py` for backend decisions

## Marker Preservation Rules

```
<!-- claude:prose -->
[Claude rewrites this content]
<!-- claude:prose:end -->
```

```
<!-- generated:start -->
[NEVER TOUCH — orchestrator-managed data]
<!-- generated:end -->
```

- The opening and closing markers must appear on their own lines, unchanged.
- Do not add extra blank lines immediately inside the markers.
- Do not nest markers.

## Warning

**NEVER modify `<!-- generated:start -->` ... `<!-- generated:end -->` blocks.**
These blocks contain auto-generated metrics and tables produced by the wiki
orchestrator. Modifying them will cause the next orchestrator run to produce
a merge conflict or silently overwrite your changes.
