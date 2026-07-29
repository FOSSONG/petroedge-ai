# Milestone 1 Hotfix

This revision fixes the failures reported after architecture consolidation.

- Added canonical RBAC roles for operator and petrophysicist.
- Retained administrator as a backwards-compatible alias for admin.
- Removed the duplicate `/platform` prefix from the platform router.
- Marked the platform route as required so startup cannot silently omit it.
- Updated API tests to use credentials loaded by Settings rather than a hard-coded password.
- Updated the health assertion to match the current `healthy` contract.
- Added regression tests for route registration and role normalisation.

No dashboard UI files are changed in this backend-only hotfix.
