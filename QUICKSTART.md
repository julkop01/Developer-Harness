# Run a complete example

Python 3.11+ is the only runtime requirement. The sample creates a temporary project and runs an actual regression check, checkpoint, review, and completion gate.

From the repository root:

```bash
python examples/walkthrough.py
```

The example does not call a model or network service. It prints the temporary workspace and a restart packet. It removes the temporary workspace when finished. Read [examples/walkthrough.py](examples/walkthrough.py) to adapt the sequence to your project.

For your own repository:

1. Ask your AI to follow [START_HERE.md](START_HERE.md).
2. Have it inspect and configure meaningful commands in `.harness/config.json`.
3. Create one task and keep its scope broad enough to include all relevant dependencies, tests, manifests, and lockfiles. Use `--scope .` when unsure.
4. Work through active → verifying → review → done. Re-run checks after edits.
5. Checkpoint before switching sessions. Start the next session with `resume TASK_ID`.

Do not start by installing a collection of optional agent libraries. The included core is functional by itself. Add an integration only when a measured bottleneck justifies it.
