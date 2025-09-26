# Copilot Instructions (Submodule: sck-core-codecommit)

- Tech: Python package (AWS CodeCommit helpers).
- Precedence: Local first, then root docs at `../../.github/...`.
- Backend conventions: `../sck-core-ui/docs/backend-code-style.md` for S3/Lambda standards.
- On conflicts, prefer local and surface a contradiction warning.

## Google Docstring Requirements
**MANDATORY**: All docstrings must use Google-style format for Sphinx documentation generation:
- Use Google-style docstrings with proper Args/Returns/Example sections
- Napoleon extension will convert Google format to RST for Sphinx processing
- Avoid direct RST syntax (`::`, `:param:`, etc.) in docstrings - use Google format instead
- Example sections should use `>>>` for doctests or simple code examples
- This ensures proper IDE interpretation while maintaining clean Sphinx documentation

## Contradiction Detection
- Check against `../sck-core-ui/docs/backend-code-style.md` and root precedence.
- If conflicting, respond with a warning, alignment options, and a concrete example.
- Example: "Using non-pinned AWS SDK versions conflicts with reproducibility guidance; pin versions in pyproject/poetry."
