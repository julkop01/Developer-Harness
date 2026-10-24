# Bounded unattended work

This playbook is for an AI host that already supports persistent/unattended sessions. Developer Harness itself does not launch models, install cron, or keep an agent alive after the host stops.

## Before starting

Record a bounded charter: owner, task IDs, allowed scope, allowed tools, external-action authorization already granted, time/check/cost limits enforced by the host, explicit stop rules, and report destination. Start with at most two approved tasks and one worker. More agents are optional; require explicit owner authorization and independent scopes/worktrees.

Use `night-plan` to select planned low/normal-risk work without unfinished dependencies. The output is a queue proposal, not permission or execution. A coordinator owns the outcome. Researcher, builder, reviewer, and reporter are roles; they do not require five simultaneously running agents.

## During work

Read the active ledger and relevant context. Inspect/implement one coherent slice. Run bounded checks. Request a separate review when required and available. Checkpoint at task boundaries, host shutdown, budget limits, or unexpected blockers. Do not repeatedly reconstruct lost context from broad repository reads.

Stop on exhausted budget, repeated unchanged failure, missing access, new sensitive/external action outside the charter, unexpected source drift, overlapping work, or inability to produce truthful proof. Preserve completed work and a concrete next step. Do not fake progress to complete a morning report.

## Handoff

Report completed work, verified evidence, blocked work and causes, decisions needed, remaining budget if known, and exact artifact/task links. Keep “implemented,” “verified,” “reviewed,” and “released” distinct. If the host stopped, report the last durable checkpoint; do not imply work continued in the background.
