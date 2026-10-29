# Issue tracker: GitHub

Issues and specs live in GitHub Issues for `fabricesemti80/home-dc`. Use the `gh` CLI from this clone, or pass `--repo fabricesemti80/home-dc` explicitly.

## Operations

- Create: `gh issue create --title "..." --body-file <file>`; use a file for multiline bodies.
- Read: `gh issue view <number> --json number,title,body,labels,comments`.
- List: `gh issue list --state open --json number,title,body,labels`; filter with `--label` as needed.
- Comment: `gh issue comment <number> --body-file <file>`.
- Apply or remove labels: `gh issue edit <number> --add-label "..."` or `--remove-label "..."`.
- Close: `gh issue close <number> --comment "..."`.

When a skill says to publish to the issue tracker, create a GitHub issue. When it says to fetch the relevant ticket, read the corresponding GitHub issue.

For parent-child tickets, use GitHub sub-issues when available; otherwise put `Part of #<parent>` at the top of the child and add a task-list link in the parent. Use native issue dependencies when available; otherwise record `Blocked by: #<number>` at the top of the dependent ticket and check whether its blockers remain open.

## Pull requests as a triage surface

**PRs as a request surface: no.**

GitHub issues and PRs share a number space. If a referenced number might be a PR, resolve it with `gh pr view <number>` before treating it as an issue.
