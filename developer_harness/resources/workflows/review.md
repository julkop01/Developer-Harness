# Challenge the result

Use after implementation and current verification. A separate context/person is preferred for material changes; high-risk and assured tasks require an independent attestation.

Read the acceptance contract, current diff/source, receipt fingerprints, relevant logs, and the simplest negative case. Check:

- Does the result solve the stated user problem?
- Do tests exercise behavior rather than mirror code or count artifacts?
- Is the criterion-to-proof mapping honest and current?
- Are compatibility, data boundaries, failure states, and rollback behavior addressed?
- Is there a simpler implementation with equivalent behavior?
- Did scope, metrics, assumptions, or authorization change silently?
- Are user-facing claims supported by actual implementation?

Record concrete findings with severity and paths. A missing blocker is not a quality score. Record `pass` only when acceptance is supported; record `fail` for material unresolved findings. Use `--independent` only when the review actually came from a separate reviewer/session, never because a different name was typed.

If review discovers a defect, move back to active, fix it, and obtain proof/review for the new fingerprint. Do not keep an old pass after source changes.
