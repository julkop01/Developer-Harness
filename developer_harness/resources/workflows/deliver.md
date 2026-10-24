# Deliver a change

Use for a feature, meaningful fix, or refactor. Keep ceremony proportional to risk.

1. Read the owner instructions, current task, relevant source, and real checks. Inspect unrelated edits before writing.
2. State the user outcome, smallest coherent scope, acceptance examples, non-goals, and failure/rollback conditions. Create a task for substantial work. Choose scopes that include dependencies, tests, manifests, and lockfiles; default to `.` if unsure.
3. Confirm the current baseline. If it fails, distinguish preexisting defects from regressions. Do not hide failures behind new labels or looser assertions.
4. Implement the smallest coherent change. Add a meaningful regression test for a real defect or new behavior when it provides useful protection. Do not write tests that only mirror implementation or count files.
5. Run appropriate named checks and map receipts to the criteria they actually demonstrate. Inspect output, diff, and relevant user behavior. Use `--no-cache` when external state or environment determines the result.
6. Move to verifying, inspect the gate, and move to review only with current proof. A passing process is necessary evidence for configured checks; it is not sufficient evidence for every product claim.
7. Obtain an appropriately independent review for high risk/assured work. If only self-review is available, label it and keep independently gated work open.
8. Complete the task after current evidence and review pass. Describe what changed, why, how it was checked, and remaining limitations. Checkpoint if the work stops earlier.

Do not expand the feature to adjacent systems without a concrete need. Changes to acceptance criteria require a replacement contract, not quiet edits to make a result look green.
