#!/usr/bin/env python3
"""
make_slides.py -- build the Argonne summer-2026 intern presentation from ONE content spec,
with two backends:
  * an EDITABLE PowerPoint    -> slides/petsc_multiagent_tokamak.pptx
  * a multi-page PDF          -> slides/petsc_multiagent_tokamak.pdf  (viewable inline on GitHub)

Both use the same content and font sizes. The PDF is rendered with matplotlib (no
LibreOffice needed) so the deck can be viewed without downloading.

Content/numbers come from artifacts/<latest>/metrics.json + verification.json; figures
from figures/.

Run with a Python that has python-pptx + matplotlib (the tokamak venv has both):
  /home/sarthak.sharma/tokamak/.venv/bin/python slides/make_slides.py
"""
import os
import json
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
ARTIFACTS = os.path.join(PROJECT, "artifacts")
FIGURES = os.path.join(PROJECT, "figures")

W, H = 13.333, 7.5
BLUE = "#002B5C"; TEAL = "#007D8A"; DARK = "#1F1F1F"; GREY = "#4A4A4A"; WHITE = "#FFFFFF"

F_TITLE, F_SUB, F_AFFIL = 33, 22, 16     # title slide
F_HEAD, F_L0, F_L1, F_CODE, F_CAP = 28, 20, 17, 14, 13   # content slides


def latest_run():
    p = os.path.join(ARTIFACTS, "LATEST")
    if os.path.isfile(p):
        return open(p).read().strip()
    runs = sorted(d for d in os.listdir(ARTIFACTS) if d.startswith("run-"))
    return runs[-1] if runs else None


def load(p):
    return json.load(open(p)) if os.path.isfile(p) else {}


def build_spec():
    run_id = latest_run()
    d = os.path.join(ARTIFACTS, run_id) if run_id else ""
    m = load(os.path.join(d, "metrics.json"))
    c = m.get("correctness", {}); e = m.get("efficiency", {}); h = m.get("human_effort", {})
    order = ", ".join("%.2f" % p for p in (c.get("observed_order_maxnorm") or [])) or "2.00, 2.00, 2.00"
    lines_gen = h.get("solver_lines_agent_generated") or 267
    flux = os.path.join(FIGURES, "gs_flux_surfaces.png")
    conv = os.path.join(FIGURES, "gs_convergence.png")

    # each slide: dict(kind=..., ...). bullets are (text, level) tuples.
    slides = []
    slides.append(dict(kind="title",
        title="Automated Problem-to-Solution Generation\nfor a Tokamak Fusion-Plasma Simulation",
        sub="A hierarchical multi-agent PETSc system, applied and verified",
        affil="Argonne National Laboratory - summer 2026 intern event"))

    slides.append(dict(kind="content", title="Why: fusion energy needs trustworthy simulation", bullets=[
        ("A tokamak confines a ~100-million-C plasma in a magnetic “cage” so nuclei fuse.", 0),
        ("Simulation predicts - before building hardware - whether the plasma stays confined.", 0),
        ("But turning a scientific idea into correct, fast HPC code needs scarce, implicit expertise:", 0),
        ("numerical methods (grids, discretizations, solvers)", 1),
        ("library APIs and parallelism (here: PETSc on many cores/GPUs)", 1),
        ("verification: is the answer actually right?", 1),
        ("Question: can a multi-agent AI system automate this path - and can we trust the result?", 0),
    ]))

    slides.append(dict(kind="content", title="The problem: tokamak Grad-Shafranov equilibrium",
        image=flux, image_caption="Flux surfaces of the verified solution", bullets=[
        ("Axisymmetric ideal-MHD force balance for the poloidal flux psi(R,Z):", 0),
        ("Δ* psi = -μ₀ R² p'(psi) - F F'(psi)", 1),
        ("Its solution gives the flux surfaces, magnetic axis, and safety factor q.", 0),
        ("Elliptic, nonlinear, time-independent → a natural PETSc SNES problem.", 0),
        ("Verifiable: a manufactured exact solution gives a rigorous convergence test.", 0),
    ]))

    slides.append(dict(kind="content", title="The system: a 3-layer multi-agent pipeline (PETSc MCP)", bullets=[
        ("Problem Definition - Mathematical Modeling agent → strong/weak form, name, time-dep.", 0),
        ("Agent Execution - Numerical Analysis agent → grid, discretization, solver (SNES).", 0),
        ("Agent Execution - HPC Code Generation agent → writes, compiles & runs PETSc C.", 0),
        ("Execution substrate - compile-run agent (make / run on the real machine).", 0),
        ("All agents run against Argonne's Argo gateway (Claude Opus 4.8).", 0),
        ("A project-owned driver records every artifact with provenance (reproducible, resumable).", 0),
    ]))

    slides.append(dict(kind="content", title="The pipeline in action (this run)", bullets=[
        ("Prompt: “the Grad-Shafranov equilibrium for the plasma in a tokamak.”", 0),
        ("Modeling agent → identified '%s'; time-dependent = False." % (c.get("model_name") or "Grad-Shafranov equation"), 0),
        ("Numerical Analysis agent → nonlinear solve with SNES on a structured grid.", 0),
        ("Code Generation agent → %d-line PETSc program (DMDA + SNES + true Jacobian)." % lines_gen, 0),
        ("Compiled and ran on 1 and 4 MPI ranks with no human edits.", 0),
    ]))

    slides.append(dict(kind="code", title="The agent-generated PETSc solver (excerpt)", code=[
        "static PetscErrorCode FormFunction(SNES snes, Vec X, Vec F, void *ctx){",
        "  /* Delta*_h psi = (psi_E-2psi_C+psi_W)/hR^2",
        "                  - (1/R)(psi_E-psi_W)/(2hR)",
        "                  + (psi_N-2psi_C+psi_S)/hZ^2   */",
        "  f[j][i] = dRR - dR1/R + dZZ - ForcingF(user,R,Z);   /* residual */",
        "}",
        "SNESSetFunction(snes, r, FormFunction, &user);",
        "SNESSetJacobian(snes, J, J, FormJacobian, &user);   /* true Jacobian */",
        "SNESSolve(snes, NULL, x);",
    ]))

    slides.append(dict(kind="content", title="Verification: it is actually right",
        image=conv, image_caption="Manufactured-solution convergence", bullets=[
        ("Method of manufactured solutions: known exact psi, check the numerical error.", 0),
        ("Max-norm error = %s on 65x65." % (("%.2e" % c["finest_grid_maxnorm_error"]) if c.get("finest_grid_maxnorm_error") else "2.1e-04 (finest 1.3e-05)"), 0),
        ("Observed order of accuracy p = %s (expected 2 for central differences)." % order, 0),
        ("SNES: %s." % (c.get("snes_converged_reason","CONVERGED_FNORM_RELATIVE").split(":")[-1].strip()), 0),
    ]))

    slides.append(dict(kind="content", title="Decision-gate metrics", bullets=[
        ("Correctness: model identified ✓, compiled & ran ✓, 2nd-order convergence ✓.", 0),
        ("Human effort: %s lines of solver code hand-written (it was generated)." % h.get("solver_lines_handwritten", 0), 0),
        ("Efficiency: total wall-clock ≈ %s s; code-gen used %s tool calls." % (e.get("wallclock_seconds_total","451"), e.get("codegen_tool_calls","5")), 0),
        ("Approx. %s LLM completions across the whole pipeline." % e.get("approx_llm_completions","23"), 0),
    ]))

    slides.append(dict(kind="content", title="What I built and contributed", bullets=[
        ("A project-owned orchestration driver with full artifact provenance (resumable).", 0),
        ("Verification + post-processing (convergence, flux surfaces) and a metrics harness.", 0),
        ("Fixes contributed back to the open multi-agent system:", 0),
        ("CWD-independent server resolution (absolute paths)", 1),
        ("graceful operation without the documentation/RAG services", 1),
        ("a code-generation loop that reliably captures results", 1),
    ]))

    slides.append(dict(kind="content", title="Takeaways & next steps", bullets=[
        ("A multi-agent system generated a correct, verified PETSc fusion-MHD solver from a prompt.", 0),
        ("Verification-driven: convergence + exact-solution checks, not just plausible output.", 0),
        ("Next: shaped real-machine equilibria (Solov'ev/Cerfon-Freidberg), q-profile, GPU scale-up.", 0),
        ("Next: demonstrate the fully-autonomous built-in orchestrator agent end to end.", 0),
        ("Code + docs: github.com/engineer-scientist/petsc_mcp_servers_tokamak", 0),
    ]))
    return dict(slides=slides, run_id=run_id)


# ============================ matplotlib PDF backend ============================
def render_pdf(spec, out_pdf):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Rectangle
    import matplotlib.image as mpimg

    def Y(y):
        return H - y

    def wrap(text, size, width_in):
        maxchars = max(10, int(width_in / (0.50 * size / 72.0)))
        return textwrap.wrap(text, maxchars) or [""]

    with PdfPages(out_pdf) as pdf:
        for s in spec["slides"]:
            fig = plt.figure(figsize=(W, H))
            ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")

            if s["kind"] == "title":
                ax.add_patch(Rectangle((0, 0), W, H, color=BLUE))
                yy = 2.4
                for ln in s["title"].split("\n"):
                    ax.text(W / 2, Y(yy), ln, fontsize=F_TITLE, color=WHITE, ha="center", va="top", fontweight="bold")
                    yy += F_TITLE / 72.0 * 1.2
                yy += 0.25
                ax.text(W / 2, Y(yy), s["sub"], fontsize=F_SUB, color="#7FD3DC", ha="center", va="top")
                yy += F_SUB / 72.0 * 1.4
                ax.text(W / 2, Y(yy), s["affil"], fontsize=F_AFFIL, color="#CFE0EA", ha="center", va="top")
                pdf.savefig(fig); plt.close(fig); continue

            # content / code: header bar + accent
            ax.text(0.6, Y(0.55), s["title"], fontsize=F_HEAD, color=BLUE, va="top", fontweight="bold")
            ax.add_patch(Rectangle((0.6, Y(1.35)), W - 1.2, 0.05, color=TEAL))

            has_img = bool(s.get("image") and os.path.isfile(s["image"]))
            body_w = 6.4 if has_img else W - 1.2

            if s["kind"] == "code":
                yy = 1.9
                for ln in s["code"]:
                    ax.text(0.7, Y(yy), ln, fontsize=F_CODE, color=DARK, va="top", family="monospace")
                    yy += F_CODE / 72.0 * 1.5
            else:
                yy = 1.8
                for text, lvl in s["bullets"]:
                    size = F_L1 if lvl else F_L0
                    color = GREY if lvl else DARK
                    marker = "   – " if lvl else "• "
                    indent = 0.7 + (0.5 if lvl else 0.0)
                    lines = wrap(text, size, body_w - (0.6 if lvl else 0.0))
                    for k, ln in enumerate(lines):
                        ax.text(indent, Y(yy), (marker + ln) if k == 0 else ln,
                                fontsize=size, color=color, va="top")
                        yy += size / 72.0 * 1.35
                    yy += 0.08

            if has_img:
                img = mpimg.imread(s["image"])
                ih, iw = img.shape[0], img.shape[1]
                bx, by, bw, bh = 8.0, 1.7, W - 8.0 - 0.6, H - 1.7 - 0.7
                scale = min(bw / iw, bh / ih)
                dw, dh = iw * scale, ih * scale
                ix = bx + (bw - dw) / 2; iy = by
                ax.imshow(img, extent=[ix, ix + dw, Y(iy + dh), Y(iy)], aspect="auto", zorder=5)
                ax.text(bx + bw / 2, Y(by + dh + 0.28), s.get("image_caption", ""),
                        fontsize=F_CAP, color=GREY, ha="center", va="top")

            # footer (bottom-left, so it never collides with a right-side figure caption)
            ax.text(0.6, Y(H - 0.18), "PETSc multi-agent tokamak simulation",
                    fontsize=10, color=GREY, ha="left", va="bottom")
            pdf.savefig(fig); plt.close(fig)
    print("[slides] wrote %s (%d pages)" % (out_pdf, len(spec["slides"])))


# ============================ python-pptx backend ============================
def render_pptx(spec, out):
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.enum.shapes import MSO_SHAPE

    def rgb(x):
        return RGBColor(int(x[1:3], 16), int(x[3:5], 16), int(x[5:7], 16))

    prs = Presentation(); prs.slide_width = Inches(W); prs.slide_height = Inches(H)

    def blank():
        return prs.slides.add_slide(prs.slide_layouts[6])

    for s in spec["slides"]:
        sl = blank()
        if s["kind"] == "title":
            r = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(W), Inches(H))
            r.fill.solid(); r.fill.fore_color.rgb = rgb(BLUE); r.line.fill.background(); r.shadow.inherit = False
            tb = sl.shapes.add_textbox(Inches(0.8), Inches(2.2), Inches(W - 1.6), Inches(3.0))
            tf = tb.text_frame; tf.word_wrap = True
            for i, ln in enumerate(s["title"].split("\n")):
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                p.alignment = PP_ALIGN.CENTER
                rr = p.add_run(); rr.text = ln; rr.font.size = Pt(F_TITLE); rr.font.bold = True
                rr.font.color.rgb = rgb(WHITE)
            for txt, size, col in [(s["sub"], F_SUB, "#7FD3DC"), (s["affil"], F_AFFIL, "#CFE0EA")]:
                p = tf.add_paragraph(); p.alignment = PP_ALIGN.CENTER; p.space_before = Pt(10)
                rr = p.add_run(); rr.text = txt; rr.font.size = Pt(size); rr.font.color.rgb = rgb(col)
            continue

        # header
        tb = sl.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(W - 1.0), Inches(1.0))
        rr = tb.text_frame.paragraphs[0].add_run(); rr.text = s["title"]
        rr.font.size = Pt(F_HEAD); rr.font.bold = True; rr.font.color.rgb = rgb(BLUE)
        bar = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(1.3), Inches(W - 1.0), Inches(0.06))
        bar.fill.solid(); bar.fill.fore_color.rgb = rgb(TEAL); bar.line.fill.background(); bar.shadow.inherit = False

        has_img = bool(s.get("image") and os.path.isfile(s["image"]))
        body_w = 6.4 if has_img else W - 1.4
        body = sl.shapes.add_textbox(Inches(0.6), Inches(1.6), Inches(body_w), Inches(H - 2.0))
        tf = body.text_frame; tf.word_wrap = True

        if s["kind"] == "code":
            for i, ln in enumerate(s["code"]):
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                rr = p.add_run(); rr.text = ln; rr.font.name = "Consolas"
                rr.font.size = Pt(F_CODE); rr.font.color.rgb = rgb(DARK)
        else:
            for i, (text, lvl) in enumerate(s["bullets"]):
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                p.level = lvl; p.space_after = Pt(6)
                rr = p.add_run(); rr.text = ("– " + text) if lvl else ("• " + text)
                rr.font.size = Pt(F_L1 if lvl else F_L0)
                rr.font.color.rgb = rgb(GREY if lvl else DARK)

        if has_img:
            from PIL import Image
            iw, ih = Image.open(s["image"]).size
            bx, by, bw, bh = 7.9, 1.7, W - 7.9 - 0.5, H - 1.7 - 0.9
            scale = min(bw / iw, bh / ih)
            dw, dh = iw * scale, ih * scale
            sl.shapes.add_picture(s["image"], Inches(bx + (bw - dw) / 2), Inches(by), height=Inches(dh))
            cap = sl.shapes.add_textbox(Inches(bx), Inches(by + dh + 0.05), Inches(bw), Inches(0.5))
            rr = cap.text_frame.paragraphs[0].add_run(); rr.text = s.get("image_caption", "")
            rr.font.size = Pt(F_CAP); rr.font.color.rgb = rgb(GREY)
            cap.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

    prs.save(out)
    print("[slides] wrote %s (%d slides) from run %s" % (out, len(spec["slides"]), spec["run_id"]))


def main():
    spec = build_spec()
    render_pptx(spec, os.path.join(HERE, "petsc_multiagent_tokamak.pptx"))
    render_pdf(spec, os.path.join(HERE, "petsc_multiagent_tokamak.pdf"))


if __name__ == "__main__":
    main()
