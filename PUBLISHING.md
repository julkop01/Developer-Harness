# Stage a GitHub release

The source archive is a clean repository root. Extract it, inspect the validation record, and create a new repository for this project. Do not overwrite an unrelated repository or push private runtime state.

With the GitHub CLI authenticated and a new repository name selected:

```bash
git init -b main
git add .
git commit -m "Release Developer Harness 1.0.0"
gh repo create OWNER/Developer-Harness --public --source=. --remote=origin --push
gh release create v1.0.0 --draft --target main --title "Developer Harness 1.0.0" --notes-file RELEASE_NOTES.md
```

Replace `OWNER` with the actual GitHub owner. Inspect the repository and draft, attach the delivered source ZIP and checksum if desired, and wait for the configured CI runs. Publish only within the owner's intended release timing.

Use `assets/github-banner.png` in the README and repository social preview. Attach `assets/x-flyer.png` to a promotion post with the verified repository/release URL. No X post is automatically sent by these instructions.

## Staging through GitHub Actions

The included `Stage draft release` workflow is opt-in: run it manually in Actions, or push the intended source commit to `release/stage-v1.0.0`. It runs the behavior tests and example, builds a deterministic ZIP and checksum, then creates a **draft** release. An existing release is left unchanged. Ordinary main-branch pushes do not stage or publish releases.

The staging job requests `contents: write` only for creating the draft and attaching its assets. Repository Actions policies may restrict it. Confirm the actual run and draft in GitHub before claiming success. Publishing the draft remains an explicit owner action.
