# Understand an existing project

Use before an import, architectural change, or unfamiliar code edit.

- Read owner instructions and Git status. Run bounded structural discovery.
- Trace one complete user journey from entry point through state/data boundaries to visible output.
- Read manifests, lockfiles, representative source, actual test assertions, CI, and deployment documentation. Avoid credential files and broad generated output.
- Identify the canonical repository, active product root, nested repositories, interface owners, and shared contracts. Keep external references separate from active code.
- Distinguish documentation claims from observed implementation. Classify each important statement as observed, inferred, proposed, or unknown.
- Identify the smallest reproducible smoke path, top concrete failure, and best next task. Test presence is not coverage, and a development build is not a verified deployment.

Output: a short architecture map, source-of-truth paths, observed baseline, top risks, and one recommendation. Continue within the already authorized task; ask only for missing decisions that materially block progress.
