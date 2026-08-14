# Macrolytics

Before making changes, read:

- CODEX_CONTEXT.md
- ARCHITECTURE.md
- README.md

## Project conventions

- Frontend: React + Vite in `frontend/`
- Data persistence: Dolt / DoltHub repository `rbasa/macroeconomia`
- ETLs live in `etl/`
- Reuse `etl/utils/db_manager.py` for database access.
- Reuse React utilities/components instead of duplicating logic.
- Do not infer economic identities unless explicitly requested.
- Prefer official source series and fixed IDs over fuzzy metadata matching.
- Keep ETL logging concise.
- Test frontend changes with `npm run build`.

# Agent Instructions

## Git safety

### Local environment

When running locally on the user's computer:

- NEVER run `git push`.
- NEVER push to `main` or to any other remote branch.
- NEVER create or modify remote branches.
- NEVER open or merge pull requests unless explicitly requested by the user.
- Local Git operations are allowed, including:
  - `git status`
  - `git diff`
  - `git log`
  - `git branch`
- The user is responsible for pushing local changes to GitHub.

This rule applies even if Git credentials are available locally and even if the
current GitHub user has permission to bypass branch protection.

### Cloud environment

When running in Codex Cloud:

- NEVER push directly to `main`.
- Start each coding task from the latest `main`.
- Create a new branch for each task.
- Use descriptive branch names prefixed with `feature/` or `fix/`.
- Commit changes to that branch.
- Push only the `feature/*` or `fix/*` branch.
- Open a pull request targeting `main`.
- NEVER merge the pull request.
- The user will review and merge the pull request manually.

## Verification

Before committing or opening a pull request:

- Review the diff.
- Run the relevant tests.
- Run the relevant build or validation commands when applicable.
- Report any failed tests or checks instead of hiding or bypassing them.