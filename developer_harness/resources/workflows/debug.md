# Debug from evidence

Use when a command, user flow, or integration behaves unexpectedly.

1. Capture the actual trigger, expected result, observed result, environment, and smallest reproduction. Preserve the failing output before changing anything.
2. Trace the relevant state/data path. Form one falsifiable hypothesis and its simplest competing explanation.
3. Run a discriminating experiment. Change one important variable at a time. Prefer local deterministic reproduction over repeated full-system retries.
4. Fix the cause, then verify the triggering case and relevant adjacent behavior. Add a regression check when it will protect a meaningful invariant.
5. Re-run after the final edit. Explain the causal link between defect, change, and proof.

If the same unchanged check fails repeatedly, the runner stops it. Treat this as a signal to inspect the hypothesis, not permission to rename the check, recreate the task, or suppress the error. Checkpoint a blocker when access or environment is missing.
