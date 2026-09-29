# Fameweb --- Development Rules

## Source of Truth

`00_PRD.md` defines product behavior.

Use: - `01_IMPLEMENTATION_PLAN.md` for build order -
`02_ARCHITECTURE.md` for system boundaries - `03_DATABASE_SCHEMA.md` for
data model - `04_API_SPEC.md` for API contracts - `05_WORK_SPLIT.md` for
parallel ownership - `06_IMPLEMENTATION_STATUS.md` for progress

## Do Not

-   Do not add a table without a concrete requirement.
-   Do not normalize JSON fields unless there is a demonstrated query
    requirement.
-   Do not store LinkedIn passwords/cookies/browser sessions.
-   Do not extend the frozen legacy LinkedIn automation.
-   Do not overwrite conversation history.
-   Do not put user-specific ICP qualification in `global_profiles`.
-   Do not silently change API contracts.
-   Do not make large unrelated UI redesigns.

## Do

-   Keep changes small and modular.
-   Reuse existing working functionality where it fits the new
    architecture.
-   Add tests around state transitions and authorization.
-   Validate all user-owned resources against the authenticated user.
-   Use parameterized DB queries/ORM.
-   Validate URLs before server-side fetching.
-   Keep SQLite compatibility while avoiding PostgreSQL-hostile design.
-   Update the relevant `.md` document when an agreed
    architecture/API/schema decision changes.

## Decision Rule

If implementation reveals a genuine requirement that is not covered: 1.
Document the gap. 2. Check whether an existing table/module can satisfy
it. 3. Only then propose a new table/module. 4. Update the
PRD/architecture docs before implementing the structural change.
