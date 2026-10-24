# Extend only where there is a real bottleneck

Personalization belongs in `.harness/config.json` and `.harness/PERSONALIZATION.md`. Add domain-specific acceptance examples, critical source paths, and boundaries there. Keep the universal kernel independent of one vendor or application category.

## Integration contract

Before connecting a crawler, gateway, database, MCP server, agent framework, or automation engine, record:

1. The concrete problem and the simpler existing alternative.
2. A pinned version, license, owner, and data boundary.
3. Inputs/outputs and the source of truth.
4. What executes code, makes network calls, costs money, or mutates external state.
5. Credentials supplied by the host, failure behavior, retries, stop limits, and rollback.
6. A meaningful contract test and a removal path.

The config inventory validates metadata; it does not load or execute integrations. An MCP or ACP bridge is a separately implemented adapter. It should call the CLI or Python API without bypassing version checks and evidence gates. The host must enforce tool permissions and actual budget limits.

## Optimization evaluation

Use a small representative task set. Record baseline and candidate completion rate, correctness, time, user intervention, tool output volume, and provider usage if known. Keep the same acceptance criteria and environment. Include failure cases, not just successful demos. Do not infer token savings from raw character counts alone.

Exact check caching is deliberately narrow. Do not add semantic answer reuse for verification claims. If you add HTTP caching, respect validators and authorization boundaries. If you add context compression, preserve source links, failure details, and the uncompressed artifact.

## Learning loop

Observe → identify a recurring failure → propose a small workflow change → compare against a baseline → review the evidence → promote the scoped lesson → revalidate it after source changes or expiry. Never let a generated summary silently rewrite project law.
