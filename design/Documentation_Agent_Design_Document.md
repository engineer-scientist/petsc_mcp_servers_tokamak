# Documentation Agent (PETSc knowledge)

> **Proposal layer:** knowledge source (not one of Fig. 2's four *specialist* agents, but an
> agent in this project's sense — every MCP server is an agent, per `MCPAgents.md`). It backs the
> proposal's "library knowledge data" (over 400 audited PETSc examples + API docs).
> **Concrete realization:** `petsc_documentation_mcp_server.py` (port **8081**). **No LLM**:
> deterministic lookup over the built PETSc HTML/Markdown docs (manual pages + users manual) plus
> an indexed search.
> **In this project:** **not available on this host** — the docs were not built
> (`$PETSC_ARCH-doc/` is absent), so the server refuses to start and the code generator omits it
> (graceful degradation, `docs/AGENT_SYSTEM_CHANGES.md` #3/#4). Documented here for completeness
> and for hosts where docs *are* built. See `docs/ENVIRONMENT.md` gotcha #2.

## External Design

**Purpose and Goal**

Gives other agents **fast, authoritative access to PETSc documentation** — manual pages, their
"See Also" cross-references, users-manual sections, and a high-quality indexed search — so a
code-generating agent can ground its API usage in real PETSc docs rather than memory. This is a
retrieval agent: exact facts, no generation.

**Scope**

* **Manual-page lookup** — return the full manual page(s) for PETSc symbols found in an input string (`get_petsc_manual_pages`).
* **Cross-reference expansion** — return the "See Also" symbols for given manual pages (`get_petsc_manual_pages_seealso`), enabling breadth-first API discovery.
* **Users-manual retrieval** — return a named chapter/section of the users manual (`get_petsc_users_manual_section`).
* **Indexed search** — return the top-N most relevant manual pages for a free-text query using PETSc's own search index (`search`).
* **Markdown normalization** — convert doc placeholders to real URLs and clean markup before returning.

**Owned concepts:** the canonical PETSc documentation corpus and how to retrieve from it.

**Out of Scope**

* No reasoning, ranking beyond the index, or synthesis — it returns documents, not answers.
* No code generation, compilation, or execution.
* Not a web search; strictly the local built docs for the configured `PETSC_DIR`/`PETSC_ARCH`.

**Inputs**

* Strings containing PETSc symbols (tokenized against a separator regex; common noise symbols like `PetscInt`, `PETSC_COMM_WORLD` are skipped) or a free-text query / section name.
* Ambient `PETSC_DIR`, `PETSC_ARCH`, and a **built** `$PETSC_ARCH-doc/` tree (with `manualpages/htmlmap`).

**Outputs**

* `get_petsc_manual_pages` → dict `{symbol: markdown}`.
* `get_petsc_manual_pages_seealso` → list of related symbols.
* `get_petsc_users_manual_section` → markdown string (or "No file named …").
* `search` → dict `{filepath: markdown}` for the top 3 hits.

**Interaction Patterns**

* A **leaf** knowledge agent, attached as a sub-server to the HPC Code Generation agent (when available) and usable by the Numerical Analysis agent for retrieval-augmented method selection.
* Read-only; never calls other agents. Callable over HTTP or stdio.

## Internal Design

**Skills List**

* **Symbol tokenization** — split input on a defined separator set, keep only tokens that are real manual-page names, and skip a curated noise list.
* **htmlmap resolution** — at startup, parse `manualpages/htmlmap` into a `{symbol → doc path}` map used by all lookups.
* **Markdown post-processing** — replace `PETSC_DOC_OUT_ROOT_PLACEHOLDER/` with `https://petsc.org/main/` and clean formatting (`petscmcp.ProcessMarkdown`).
* **"See Also" parsing** — extract the `## See Also` block from a page and normalize it to a symbol list.
* **Indexed search delegation** — call PETSc's own `search.searchDocsIndex` (from `$PETSC_DIR/lib/petsc/bin`).

**Tool List**

* `get_petsc_manual_pages(string) → dict`
* `get_petsc_manual_pages_seealso(string) → list`
* `get_petsc_users_manual_section(section) → str`
* `search(string) → dict`
* **No LLM.** Pure Python file/index lookups.

**Validation Techniques**

* **Startup gate** — refuses to start unless `$PETSC_ARCH-doc/` exists (`RuntimeError: ... documentation was not built`), so callers never get half-working doc tools.
* **Existence checks** — missing section files return an explicit "No file named …" rather than raising.
* **Noise filtering** — the skip-list and dedup prevent returning trivial or duplicate pages.
* **URL/markup normalization** — ensures returned links are valid public URLs.

**Required Logging**

* Each request logs what was requested and which files were opened; missing "See Also" blocks are logged.
* When attached to the code generator, its results appear in that agent's transcript.

## Additional Information

* **Why it's off here.** Building the HTML/Markdown docs (`make alldoc`) is heavy and wasn't done
  on this compute node, so `$PETSC_ARCH-doc/` is absent. This project's contribution
  (`documentationAvailable()` probe + code-gen degradation) lets the pipeline run *without* it,
  attaching only servers that can actually start (`docs/AGENT_SYSTEM_CHANGES.md` #3, #4).
* **Relationship to RAG.** Documentation is exact retrieval by symbol/section/index; the **RAG**
  agent (port 8082) is semantic retrieval + reranking over embedded docs. They are complementary
  knowledge agents; both are optional sub-servers of the code generator.

## Failure Modes

* **Docs not built** — server won't start; the whole class of doc tools is unavailable (handled by graceful degradation upstream).
* **Symbol not in htmlmap** — a requested symbol silently yields nothing; a caller may misread absence as "no such API." Mitigation: pair with `search`/RAG.
* **Stale docs** — the built docs lag the installed PETSc version, returning outdated signatures. Mitigation: rebuild docs with the arch.
* **Search index absent/incompatible** — `search.searchDocsIndex` unavailable for the build; the `search` tool fails. Mitigation: ensure the index ships with the built docs.
* **Malformed page markup** — a page missing `## See Also` or with unexpected formatting yields empty/partial results (logged).
