# RAG Agent (retrieval-augmented PETSc knowledge)

> **Proposal layer:** knowledge source (an agent in this project's sense — every MCP server is an
> agent, per `MCPAgents.md`). Realizes the proposal's **retrieval-augmented PETSc knowledge
> access** (petsc-ai.org) that the Numerical Analysis and Code Generation agents lean on.
> **Concrete realization:** `petsc_rag_mcp_server.py` (port **8082**). Uses ML models (**not** a
> chat LLM): NVIDIA embeddings (`nvidia/nv-embed-v1`) over two Chroma vector stores
> (documentation + developer) with an NVIDIA reranker (`nv-rerank-qa-mistral-4b`). Returns
> context strings to be injected into a *caller's* LLM prompt.
> **In this project:** **not available on this host** — needs `NVIDIA_API_KEY`, a `rag-data/`
> corpus, and langchain deps that aren't installed; the code generator omits it (graceful
> degradation, `docs/AGENT_SYSTEM_CHANGES.md` #3/#4). Documented for completeness and for
> provisioned hosts. See `docs/ENVIRONMENT.md` gotcha #3.

## External Design

**Purpose and Goal**

Provides **semantically relevant PETSc context** for a natural-language request — the RAG
("retrieval-augmented generation") half of grounding: find the passages in the PETSc corpus most
relevant to a question, rerank them for quality, and hand them back as a prompt-ready string so
the *calling* agent's LLM answers with real PETSc knowledge instead of hallucinating APIs.

**Scope**

* **Documentation RAG** — given a request, retrieve+rerank passages from the embedded PETSc **documentation** corpus (`get_documentation_rag_prompt`).
* **Developer RAG** — the same over the PETSc **developer** corpus (source/design knowledge) (`get_developer_rag_prompt`).
* **Retrieve → rerank → dedup** — base retriever returns top-k (k=8), the reranker reduces to the best top-n (n=4), duplicate passages are dropped, and the survivors are concatenated into one context string.

**Owned concepts:** the embedded PETSc corpora and the retrieval/rerank pipeline over them.

**Out of Scope**

* Does **not** answer the question itself — it returns *context*, not a completion. The consuming agent's LLM does the reasoning.
* No code generation, compilation, or execution.
* No exact symbol lookup (that's the **Documentation** agent) — RAG is semantic/approximate.

**Inputs**

* A free-text `request` string.
* Ambient config: `NVIDIA_API_KEY`, the `rag-data/documentation-*` and `rag-data/developer-*` Chroma directories (built from the corpus), and the embedding/rerank endpoints.

**Outputs**

* A single string of concatenated, de-duplicated, reranked passages, intended to be prepended to a caller's LLM prompt (empty/`'Unknown RAG data type'` on misuse).

**Interaction Patterns**

* A **leaf** knowledge agent, attached (when available) as a sub-server to the HPC Code Generation agent and usable by the Numerical Analysis agent for retrieval-augmented method selection.
* Read-only w.r.t. other agents; it does call external NVIDIA endpoints for embeddings/reranking. Callable over HTTP or stdio.

## Internal Design

**Skills List**

* **Corpus selection** — route `documentation` vs `developer` requests to the right vector store.
* **Embedding + vector retrieval** — embed the request and pull top-k candidates from Chroma.
* **Reranking** — apply `NVIDIARerank(nv-rerank-qa-mistral-4b, top_n=4)` (a FlashRank fallback exists) to keep the most relevant passages.
* **Context assembly** — drop consecutive duplicates and concatenate into a clean prompt string.

**Tool List**

* `get_documentation_rag_prompt(request) → str`
* `get_developer_rag_prompt(request) → str`
* **Models (not a chat LLM):** NVIDIA embeddings `nvidia/nv-embed-v1`; reranker `nv-rerank-qa-mistral-4b:1`; vector DB Chroma; libs `langchain*`, `flashrank`.

**Validation Techniques**

* **Startup key check** — requires `NVIDIA_API_KEY` (`serverCheckKey`); refuses to start otherwise.
* **Corpus presence check** — raises if the `rag-data/...` Chroma directories are missing, so it never serves an empty index.
* **Dedup** — identical passages are collapsed to avoid redundant context.
* **Type guard** — unknown corpus type returns an explicit message rather than wrong data.
* *(Quality)* the retrieve-k-then-rerank-to-n design is itself a precision guard: broad recall, then quality filtering.

**Required Logging**

* Each request is logged (`get_documentation_rag_prompt() request received: ...`).
* When attached to the code generator, the returned context and its use appear in that agent's transcript.

## Additional Information

* **Why it's off here.** No `NVIDIA_API_KEY`, no `rag-data/` corpus, and langchain/NVIDIA deps
  aren't installed in the `mcp-test` venv. This project's `ragAvailable()` probe + code-gen
  degradation let the pipeline run without it (`docs/AGENT_SYSTEM_CHANGES.md` #3, #4).
* **Building the corpus.** `petsc_rag_mcp_generate_data.py` + `utils/createembedding.py` build the
  Chroma stores from PETSc docs/source (over 400 PETSc examples per the proposal's corpus
  description).
* **RAG vs Documentation.** Use **Documentation** (8081) for exact symbol/section lookup; use
  **RAG** (8082) for "what's the right approach to X?" semantic context. The two are
  complementary optional knowledge sub-servers of the code generator.
* **Phase II.** The proposal extends this from static library knowledge to *learned* relationships
  from accumulated simulation telemetry (via the Persistent Memory agent), improving method
  selection over time.

## Failure Modes

* **Missing key/corpus/deps** — server won't start or can't retrieve; handled by graceful degradation upstream (the code generator simply omits it).
* **Low-relevance retrieval** — embeddings/reranker surface off-target passages, injecting misleading context into the caller's prompt. Mitigation: reranking + dedup; tune k/top_n; combine with exact Documentation lookup.
* **Stale index** — the embedded corpus lags the installed PETSc version, so context describes outdated APIs. Mitigation: rebuild the vector stores when PETSc updates.
* **External-endpoint dependency** — NVIDIA embedding/rerank endpoints unavailable or rate-limited stalls retrieval. Mitigation: FlashRank local fallback; caching.
* **Context bloat** — returning too much/redundant text crowds the caller's prompt. Mitigation: top_n cap + dedup.
