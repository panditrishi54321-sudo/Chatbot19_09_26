# SkillSpring — Architecture Rules

## Purpose
Use this prompt before making architectural or cross-file changes to the SkillSpring Flask EdTech application.

## Rules
- Inspect the existing project before changing code.
- Do NOT rebuild the application from scratch.
- Preserve the existing Flask architecture unless a change is explicitly requested.
- Preserve existing routes and working functionality.
- Reuse existing services, helpers, templates, CSS classes, IDs and JavaScript behaviour where possible.
- Do not silently rename files, folders, routes, functions, database tables or API fields.
- Do not change the SQLite schema unless the requirement explicitly needs it.
- Keep secrets in `.env`; never hard-code API keys.
- Keep frontend and backend responsibilities separate.
- Validate changes with the running application after implementation.
- Prefer the smallest safe change that solves the requested problem.
- If a requested change conflicts with the existing architecture, explain the conflict before changing architecture.

## Required response format
1. What was inspected
2. Root cause or requirement
3. Files that need changes
4. Minimal implementation plan
5. Code changes
6. Validation steps
7. Risks or follow-up items
