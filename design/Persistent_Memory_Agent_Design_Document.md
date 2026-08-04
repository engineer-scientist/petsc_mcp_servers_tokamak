# Persistent Decision-Aware Memory Agent

> **Proposal layer:** Workflow Control (McInnes et al., DE-FOA-0003612, Fig. 2 —
> *Persistent Decision-Aware Memory* [Context, Decisions], paired with the Orchestrator and
> the Shared Memory [Tools, Compilers, Models]).
> **Status:** a **Phase-I gap this project fills** — there is **no MCP server for it yet** in
> `petsc_mcp_servers` (see `docs/ARCHITECTURE.md` "Not yet present: Persistent, decision-aware
> memory of structured artifacts across runs"). This document is **design-forward** and grounds
> the agent in the concrete store this project already maintains.
> **Current realization in this project (to be agent-ified):** the `artifacts/<run-id>/` store
> written by `src/orchestrate_tokamak.py` — per-stage inputs, transcripts, structured outputs,
> `DATAFLOW.md` lineage, `metrics.md`, `README.md`, and the `LATEST` pointer (schema in
> `artifacts/README.md`).

## External Design

**Purpose and Goal**

Retains the key artifacts produced by every agent across every run **and surfaces the
information most relevant to downstream decisions** — not a dumb log, but a *decision-aware*
memory. The proposal makes this the substrate for the system's two defining behaviors:
**rollback/replan** (back up to a validated earlier state) and **self-improvement** (reuse prior
plans, solver configurations, and *failure cases* so later runs are better and cheaper). It is
what turns a one-shot pipeline into an accumulating body of "structured artifacts."

**Scope**

* **Artifact retention** — durably store each stage's structured output (model spec, numerical plan, generated code + run output, verification diagnostics) plus provenance (inputs, transcripts, timestamps, model/version).
* **Lineage** — record how each artifact derived from the previous (the `DATAFLOW.md` map: request → model → NA decision → code → run → verification).
* **Decision-aware retrieval** — given the current stage and problem characteristics, return the *most relevant* prior context: similar past problems, the plan/solver config that worked, and known failure cases to avoid.
* **Run indexing** — track runs, their status, and a canonical/`LATEST` pointer; make runs queryable and comparable (metrics across runs).
* **Failure memory** — retain informative failure cases ("this solver config diverged on this problem class") to steer future decisions away from antipatterns.

**Owned concepts:** the durable record of what happened, why, and what to reuse. It is the
single source of truth for "what did we decide, and what came of it?"

**Out of Scope**

* Does not make modeling/numerical/coding decisions — it stores them and surfaces relevant priors.
* Does not control the workflow — the Orchestrator does; this agent serves the Orchestrator (and, read-only, the specialists).
* Does not itself judge scientific correctness — it stores the Visualization & Analysis agent's verdicts.

**Inputs**

* From the Orchestrator/driver and each specialist: structured artifacts to persist (with keys, provenance, and the producing stage).
* Retrieval queries: "given this specification / this stage, what prior context is relevant?"
* Distinguishes **Shared Memory** (relatively static tools/compilers/models registry) from **run memory** (per-run context and decisions).

**Outputs**

* On write: an artifact id / path and confirmation.
* On read: the requested artifacts and a **ranked, decision-relevant** context bundle (prior plans, configs, similar cases, failures) for the querying stage.
* Aggregate views: run index, cross-run metrics, `LATEST`.

**Interaction Patterns**

* Written to by the Orchestrator at each stage boundary; read by the Orchestrator (for rollback/replan) and, read-only, by specialists that want prior context (e.g., the NA agent asking "what solver worked for a similar elliptic nonlinear problem?").
* On **rollback**, provides the last validated artifacts so the Orchestrator can resume from a known-good state instead of restarting.
* Over time enables the **self-improving** loop: accumulated artifacts feed Phase-II learned method selection (the NA agent's "learned relationships from simulation telemetry").
* When built as an MCP server it would expose read/write tools; today the driver reads/writes the `artifacts/` tree directly.

## Internal Design

**Skills List**

* **Structured write** — persist an artifact with a stable schema (stage, keys, provenance, timestamp, model id) under `artifacts/<run-id>/`, never clobbering prior runs.
* **Lineage capture** — append to the run's `DATAFLOW.md` the edge from producer to product.
* **Relevance retrieval** — select prior artifacts by problem similarity, stage, and outcome; rank by usefulness to the current decision (Phase II: embeddings over problem descriptions + telemetry).
* **Metrics rollup** — compute/store per-run and cross-run metrics (loops, tool calls, wall-clock, human-edit lines, observed order) as `metrics.md`.
* **Run pointer management** — maintain `LATEST` and canonical-run markers, being careful that consumers expecting a particular schema aren't pointed at an incompatible run (a real gotcha: `LATEST` was deliberately kept on the driver run because verify/metrics expect the driver schema, not the orchestrator-demo schema — see `docs/SESSION_LOG.md`).
* **Failure-case curation** — tag and index runs/stages that failed, with the reason, for antipattern avoidance.

**Tool List**

* *(When built)* MCP tools such as `store_artifact(run_id, stage, data)`, `get_artifact(run_id, stage)`, `query_relevant(spec, stage)`, `list_runs()`, `get_metrics(run_id)`.
* Backing store: the filesystem `artifacts/` tree today (JSON/Markdown/logs); a database (as the proposal envisions "stored in a database accessible by the orchestrator") in future.
* Phase II: an embedding/similarity service for decision-aware retrieval.

**Validation Techniques**

* **Schema conformance** — reject/repair artifacts that don't match the documented schema (`artifacts/README.md`), so downstream tools (verify, metrics) can rely on structure.
* **Immutability of prior runs** — new runs never overwrite old ones (unique run-ids); `LATEST` moves, history does not.
* **Provenance completeness** — every artifact must carry its producing stage, input, and model/version; a stage that fails to record these is flagged.
* **Retrieval relevance sanity** — surfaced priors must actually match the query's problem class/stage (guard against returning misleading "similar" cases).

**Required Logging**

* Itself the logging substrate: it *is* where inputs, transcripts, decisions, code, outputs, diagnostics, lineage, and metrics live.
* Should additionally log its own read/write operations and retrieval decisions (what prior context it surfaced and why) for auditability of the self-improving loop.

## Additional Information

* **Why "decision-aware," not just "storage."** The value is in *surfacing the right prior at
  the right moment* — the plan that worked, the config that diverged — so the Orchestrator and
  specialists make better decisions with less compute. Plain logs don't do this.
* **Already the proposal's "accumulated structured artifacts."** This project's `artifacts/`
  store, with per-stage transcripts and a `DATAFLOW.md` lineage map, is exactly the substrate
  the proposal describes; formalizing it as an MCP server (with retrieval) is the remaining step
  (`docs/ROADMAP.md` §"Add persistent artifact memory").
* **Cold-start.** The proposal notes the risk of scarce accumulated artifacts and seeds the
  store with expert-curated PETSc exemplars; the same applies here for retrieval to be useful
  early.

## Failure Modes

* **Clobbering / lost history** — a shared or reused path overwrites a prior run's artifacts (cf. the shared compile-run work dir gotcha). Mitigation: unique run-ids, immutable prior runs.
* **Schema drift** — an artifact whose shape a later run changed breaks verify/metrics consumers. Mitigation: schema conformance checks; version the schema; keep `LATEST` on a compatible run.
* **Misleading retrieval** — surfacing an irrelevant "similar" case that steers a wrong decision. Mitigation: relevance sanity checks; conservative ranking; include outcome (success/failure) in the signal.
* **Incomplete provenance** — an artifact stored without its input/model/version, so it can't be reproduced or trusted for reuse. Mitigation: provenance-completeness gate on write.
* **Stale/large store** — unbounded growth or stale entries degrade retrieval. Mitigation: indexing, curation, and failure-case tagging.
* **Privacy/leakage** (Phase II, cloud) — retained context could leak across users/tenants. Mitigation: per-tenant isolation and access control (the proposal's caveat on stateful cloud agents).
