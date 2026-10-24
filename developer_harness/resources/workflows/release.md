# Prepare a release

Make the result concrete and reviewable before an approval request that is actually required by the owner or host.

1. Confirm the release scope, source commit, version, compatibility, and remaining blockers.
2. Run the appropriate regression suite, packaging check, and the real user smoke path. Inspect the packaged artifact from a clean extraction, not only the working tree.
3. Check generated/readme claims against capabilities. Confirm licenses, third-party asset attribution, private-data exclusions, and configuration defaults.
4. Record exact validation environment, check results, known gaps, migration notes, and rollback steps.
5. Produce the archive, checksums, release notes, and a draft release/PR when authorized. Preserve protected branches and do not force-push unrelated work.
6. Publish, merge, or deploy only within explicit authorization. Existing authorization persists; do not ask again merely because a workflow mentions approval.

A green task is not a deployed system. A prepared CI matrix is not a passed CI run. A draft release is not a public release. Say exactly which stage was reached.
