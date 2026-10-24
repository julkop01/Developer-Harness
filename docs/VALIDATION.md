# Release validation

The final validation record is generated during packaging and included as `RELEASE_VALIDATION.json`. It records the actual Python/platform, commands, exit codes, and test counts. Do not infer hosted CI results from the presence of a workflow file.

The behavioral suite exercises real temporary workspaces: install/update/uninstall, owner-rule preservation, managed-file conflicts, task transitions and concurrency versions, evidence freshness, config/source/log drift, acceptance gates, manual observation labels, review requirements, exact check reuse, failures, time/output bounds, reduced environment, memory provenance/supersession, advisory leases, usage deduplication, event integrity, and backup restoration.

The complete example exercises the user loop from contract through checks, checkpoint, review, and done. Release checks validate links, distribution contents, Python syntax, profiles, version consistency, and the absence of runtime state. A clean extracted archive is tested before delivery.

Limitations: local validation cannot establish every host integration, model behavior, independent identity, true provider budgets, network isolation, or all target-platform behavior. CI is configured for Python 3.11–3.13 on Linux, Windows, and macOS. Inspect actual run results after pushing to GitHub.
