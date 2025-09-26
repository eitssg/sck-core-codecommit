# Copilot Instructions (Submodule: sck-core-codecommit)

- Tech: Python package (AWS CodeCommit helpers).
- Precedence: Local first, then root docs at `../../.github/...`.
- Backend conventions: `../sck-core-ui/docs/backend-code-style.md` for S3/Lambda standards.
- On conflicts, prefer local and surface a contradiction warning.

## RST Documentation Requirements
**MANDATORY**: All docstrings must be RST-compatible for Sphinx documentation generation:
- Use proper RST syntax: `::` for code blocks (not markdown triple backticks)
- Code blocks must be indented 4+ spaces relative to preceding text
- Add blank line after `::` before code content
- Bullet lists must end with blank line before continuing text
- Use RST field lists for parameters: `:param name: description`
- Use RST directives: `.. note::`, `.. warning::`, etc.
- Test docstrings with Sphinx build - code is source of truth, not docstrings

## Contradiction Detection
- Check against `../sck-core-ui/docs/backend-code-style.md` and root precedence.
- If conflicting, respond with a warning, alignment options, and a concrete example.
- Example: "Using non-pinned AWS SDK versions conflicts with reproducibility guidance; pin versions in pyproject/poetry."
