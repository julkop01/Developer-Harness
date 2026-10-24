# Personalize Developer Harness

This is the AI-facing onboarding protocol. Read this file when the user requests installation, import, or personalization. Do not make a beginner learn the internals.

## 1. Understand the intended result

Extract from the conversation: intended outcomes, active projects, tools, stack, operating system, communication language, experience, constraints, and acceptable autonomy. Reuse stated preferences. Ask at most two targeted questions only if a missing choice changes the result. A generic profile is a valid starting point; do not block useful setup on a long interview.

Distinguish three entry modes: new workspace, existing repository, and continuing workspace. Read existing project instructions and inspect Git status before editing. Preserve unrelated work. Never import domain assumptions, product names, or personal history from the harness author.

## 2. Inspect before selecting a profile

Use `discover` for a bounded structural map. Open the real manifests, source entry points, tests, and CI definitions. Do not read private configuration or credential files. Test filenames are clues, not coverage. Write down what is observed, inferred, and unknown.

Choose general, web-api, data-research, automation, library-cli, or assured. The profile sets defaults and focus; it does not certify the project. The owner may customize `.harness/config.json` and create `.harness/PERSONALIZATION.md` with domain-specific guidance.

## 3. Apply the repository-local setup

From a source checkout, use `python dh.py --root TARGET install ...` to inspect the write plan, then `--apply` within the user's already authorized installation request. Use `init` when this checkout is the working project. The installed entry point is `python .developer-harness/dh.py`; use it for all target-project commands.

Keep existing AGENTS/CLAUDE/GEMINI/Copilot content outside the managed block. Select optional adapters only for tools the owner actually uses. Do not edit global settings, install dependencies, enable remote services, create background jobs, or infer purchase authorization. If a managed file conflicts, preserve the local change and explain the specific conflict.

## 4. Configure checks from observed reality

Read the actual scripts and test configuration. Set `commands` to executable argument arrays with descriptions and timeouts. Use `{python}` for this interpreter. Add `required_checks` only for meaningful project validation. A working repository usually needs a regression/unit check and its smallest end-to-end smoke path. Do not use `echo success` or file-existence checks to stand in for behavior.

Configure the communication preferences and choose a practical context budget. Default external budget is zero; the CLI never calls a model or gateway. Model selection and provider limits stay with the host. Do not change the owner's autonomy boundaries because a profile suggests a stricter or looser workflow.

## 5. Write a short personalization record

Create `.harness/PERSONALIZATION.md` with:

- purpose, owner, language, and working style;
- chosen profile and reasons;
- source-of-truth paths, stack, commands, and their verification status;
- privacy, tool-access, deployment, and external-action boundaries;
- known unknowns, one immediate task, and the next useful milestone.

Record real values. If a command could not run, mark it unverified and state the blocker. User preferences are preferences; do not promote them as experimentally proven findings.

## 6. Prove the installation

Run `doctor`. Create one small task with a real outcome, acceptance criteria, explicit scope, and an owner. Execute an appropriate configured check if the environment supports it. Create a checkpoint and generate `resume` to verify continuity. Keep the first task open if product acceptance has not actually been met.

Report what was installed, what was personalized, what passed, what remains unknown, and how the user starts the next session. Prefer a short plain-language response. Do not claim a background agent or automatic deployment was enabled.

## Everyday startup

Read `.harness/config.json`, `.harness/PERSONALIZATION.md` when present, the active task, and its restart packet. Load the relevant workflow only. Inspect changed source files before editing. For a simple question or tiny reversible edit, use proportionate ceremony. For substantial behavior changes, use the task and evidence gates.
