# Release policy

- **Semantic versioning** for the package and, separately, for the contract schema
  (`CONTRACT_SCHEMA_VERSION`). A contract MAJOR bump requires a storage migration and an SDK
  major bump.
- **Changelog**: `CHANGELOG.md` (Keep a Changelog format), updated with every user-visible change.
- **Migrations**: numbered SQL migrations under `src/evalkit/storage/migrations/`, applied by
  `evalkit db migrate`, each with a downgrade or a documented reason why not. Backup before
  migrate (`docs/RUNBOOK.md`).
- **Compatibility tests**: CLI ↔ API ↔ SDK on the same scenario; schema diff check against
  the previous release's exported schemas.
- **Security checks**: `pip-audit`, `npm audit`, dependency inventory (SBOM via CycloneDX)
  attached to each release.
- **Rollback**: previous wheel/image/tag remain available; data restore procedure in RUNBOOK.
- **Publication** to PyPI, npm, registries or GitHub is a level-4 action: never automatic.
