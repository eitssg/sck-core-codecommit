# Copilot Instructions (Submodule: sck-core-codecommit)

- Tech: Python package (AWS CodeCommit helpers).
- Precedence: Local first, then root docs at `../../.github/...`.
- Backend conventions: `../sck-core-ui/docs/backend-code-style.md` for S3/Lambda standards.
- On conflicts, prefer local and surface a contradiction warning.

## Contradiction Detection
- Check against `../sck-core-ui/docs/backend-code-style.md` and root precedence.
- If conflicting, respond with a warning, alignment options, and a concrete example.
- Example: "Using non-pinned AWS SDK versions conflicts with reproducibility guidance; pin versions in pyproject/poetry."
