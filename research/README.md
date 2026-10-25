# Research and design basis

Reviewed 2026-10-25. This is a design comparison, not a benchmark claiming superiority over another framework. The implementation is original and bundles no third-party agent framework code.

## What changed in harness practice

The useful shift is from long universal prompts toward smaller instructions, persistent work state, executable checks, explicit recovery, and separate evaluation. A local control plane should distinguish what the model reasons about from what code can actually enforce. These patterns inform this release; they do not prove a performance gain without project-level evaluation.

| Primary source | Relevant practice | Decision in this release |
| --- | --- | --- |
| [Anthropic: long-running harnesses](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents), 2025-11-26 | Incremental tasks and durable session handoffs | Checkpoints, task contracts, resume packets |
| [Anthropic: application harness design](https://www.anthropic.com/research/harness-design-long-running-apps), 2026-03-24 | Structured handoff and evaluation separate from generation | Current proof gates and explicit review; no universal quality score |
| [OpenAI: project instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md) | Scoped repository instructions and bounded startup context | Small AGENTS entry point and owner-rule-preserving overlay |
| [OpenAI: build skills](https://learn.chatgpt.com/docs/build-skills) and [Agent Skills specification](https://agentskills.io/specification) | Progressive loading of metadata, instructions, and resources | Load focused playbooks on demand; avoid an oversized mandatory startup stack |
| [Superpowers](https://github.com/obra/superpowers) | Composable engineering workflows and verification discipline | Focused deliver/debug/review playbooks; ceremony proportional to the task |
| [GitHub Spec Kit](https://github.github.com/spec-kit/reference/agentic-sdd.html) | Specifications, implementation plans, and consistency checks | Acceptance contract with explicit scope and proof mapping |
| [Open GSD Core](https://github.com/open-gsd/gsd-core) | Phase-oriented context management and durable state artifacts | Bounded restart packs; single-agent operation remains sufficient |
| [OpenHands SDK](https://github.com/OpenHands/software-agent-sdk) | Separate agent/runtime/workspace responsibilities | Host owns execution isolation and model lifecycle |
| [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | Distinguish checkpoints from long-term state | Session checkpoints and reviewed memory have different lifecycles |
| [OpenCode permissions](https://opencode.ai/docs/permissions/) | Explicit tool permission boundaries | Do not treat project instructions or local task state as tool authorization |
| [MCP security guidance](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices) | Minimize trust and privilege across tool boundaries | Integration ownership and data boundaries; untrusted content cannot grant authority |
| [ECC](https://github.com/affaan-m/ECC) | Cross-harness session normalization, MCP inventory, worktree lifecycle, operator surfaces | Adopt the useful control-plane patterns behind stricter local evidence/provenance boundaries; do not copy catalog size as a goal |

The former `gsd-build/get-shit-done` repository is archived and points to Open GSD Core. Canonical locations and maintenance status matter more than a screenshot's popularity. All external links and product behavior can change; revalidate before integrating.

## Lessons retained from earlier source review

Two owner-supplied repository baselines were inspected at fixed revisions, including their startup rules, constitutions, runtime scripts, memory protocols, onboarding, and health checks. Review was focused on the harness layer; it was not an exhaustive application audit or a live deployment test. Private source snapshots and project identifiers are excluded from this public distribution.

Useful foundations: read before editing, narrow changes, truthful labels, separation of observations from decisions, simple baseline challenges, and explicit handoffs. The main improvement targets were large mandatory reading stacks, file-presence checks that could be mistaken for behavioral validation, approximate static context budgets, domain coupling, and runtime labels that exceeded their implementation.

The 2.0 design uses actual task transitions, source-bound proof, bounded runner behavior, canonical host contracts, persistent session/event observations, MCP drift detection, read-only worktree lifecycle analysis, a unified control-plane projection, explicit capability boundaries, and documented recovery. This is an architectural improvement claim with tested mechanisms, not a measured claim that every AI task becomes faster or better.

## Screenshot: team director

Adopted as operating ideas: one accountable coordinator, concrete researcher/builder/reviewer/reporter outputs, explicit state, bounded queue, checkpointing, and a final evidence-based handoff. Roles do not imply a mandatory multi-agent system. The core's `night-plan` prepares a queue; an authorized host must actually execute or schedule it.

## Screenshot: low-cost toolkit

The screenshot lists complementary tools, not twenty required dependencies. Their useful principles can often be implemented more simply in a repository workflow. These are integration candidates and evaluation decisions, not claims that the core contains working adapters for them.

| Named tool | Useful idea | Starting decision |
| --- | --- | --- |
| Crawl4AI | Convert fetched pages to useful text | Optional research ingestion; host/network permissions required |
| Firecrawl | Structured web extraction | Optional when ordinary source retrieval is insufficient |
| Chonkie | Split documents into retrievable chunks | Defer until document volume justifies it |
| FlagEmbedding | Rerank candidate evidence | Add only after keyword/source-pointer retrieval is measured to fail |
| LLMLingua | Compress input context | Defer; retain raw source and failure detail when evaluating |
| RTK | Reduce repetitive command-output volume | Core bounds output; evaluate a separate filter if needed |
| GPTCache | Reuse prior results | Core caches exact successful checks; semantic reuse cannot establish verification |
| Portkey Gateway | Centralize model calls and observability | Optional host-side gateway; never mandatory for local operation |
| Prefect | Persist and orchestrate workflows | External integration when actual distributed orchestration is needed |
| Mem0 | Select durable cross-session facts | Core uses explicit candidate/decision records and scoped retrieval |
| Graphiti | Track provenance and changing facts | Core retains expiry/supersession; defer graph infrastructure |
| requests-cache | Cache HTTP results with freshness rules | Optional research adapter; never cache authorization or verification blindly |
| Hishel | Respect HTTP caching semantics | Optional, with validators and per-identity data boundaries |
| APScheduler | Schedule bounded local work | Host-owned; core does not pretend a queue is a scheduler |
| Celery | Worker queues and background processes | Defer until distributed execution is an actual requirement |
| PyBreaker | Stop repeated dependency failures | Core stops repeated unchanged check failures |
| LiteLLM | Route calls and track model usage | Optional provider layer; real spending controls live there |
| RouteLLM | Choose models by task/cost | Host-side experiment with acceptance and quality measurements |
| Semantic Router | Route simple requests without an LLM | Defer until there is a stable workload and evaluation set |
| Phoenix | Trace and inspect expensive/failed work | Core records local receipts/events; optional external observability |

Selected tool sources inspected directly: [RTK](https://github.com/rtk-ai/rtk), [Graphiti](https://github.com/getzep/graphiti), [LiteLLM](https://github.com/BerriAI/litellm), and [Crawl4AI](https://github.com/unclecode/crawl4ai). The remaining rows evaluate the ideas described in the supplied screenshot; they are not a current license/security audit of those packages. Verify versions, licenses, privacy, cost, and maintenance before use. For example, an adjacent proxy component can have a different license from its CLI.

## What 2.0 now implements

The earlier research targets around normalized host state, MCP fragmentation/drift, and worktree lifecycle are no longer just design candidates. Version 2.0 has strict `dh.session.v1`, `dh.tool_event.v1`, `dh.context.v1`, `dh.permission.v1`, and `dh.mcp.v1` contracts; persistent host observation and MCP inventory tables; secret-value rejection for MCP metadata; read-only Git worktree lifecycle/conflict analysis; and a unified read-only operator snapshot.

These features remain deliberately separated from authority. A permission observation does not grant permission, a tool event is not acceptance evidence, MCP inventory does not start a server, and a cleanup plan does not delete a worktree.

## Candidate improvements to evaluate later

1. Real native Codex/Claude/OpenCode/Gemini bridges that emit the canonical contracts, each with version and permission contract tests.
2. Optional sandbox execution with a clear filesystem/network policy.
3. Provider-reported cost collection and enforced reservations in a gateway.
4. Portable human-readable memory projection and retrieval benchmarks before embeddings or semantic compression.
5. Independent human/CI-signed proof for workflows needing stronger identity assurance.
6. A thin local HUD/dashboard consuming the read-only control-plane JSON without creating a second state authority.

These are extension directions, not unfinished features advertised as already working.
