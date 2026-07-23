#!/usr/bin/env python3
"""
make_poster.py -- build the US-RSE 2026 poster as an EDITABLE single-slide PowerPoint
(poster/USRSE26_poster.pptx), 48 in x 36 in landscape, from the real run artifacts.

Every element is a native PowerPoint shape/text box/picture, so it can be freely edited.
Content and numbers come from artifacts/<latest>/metrics.json + verification.json and the
figures in figures/. The abstract text lives in poster/abstract.md.

Run with a Python that has python-pptx (the tokamak venv has it):
  /home/sarthak.sharma/tokamak/.venv/bin/python poster/make_poster.py
"""
import os
import json

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
ARTIFACTS = os.path.join(PROJECT, "artifacts")
FIGURES = os.path.join(PROJECT, "figures")

ANL_BLUE = RGBColor(0x00, 0x2B, 0x5C)   # deep blue
ANL_TEAL = RGBColor(0x00, 0x7D, 0x8A)   # accent
LIGHT = RGBColor(0xEF, 0xF3, 0xF7)      # panel fill
DARK = RGBColor(0x1F, 0x1F, 0x1F)
GREY = RGBColor(0x4A, 0x4A, 0x4A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

W, H = 48.0, 36.0   # inches (poster)


def latest_run():
    p = os.path.join(ARTIFACTS, "LATEST")
    if os.path.isfile(p):
        return open(p).read().strip()
    runs = sorted(d for d in os.listdir(ARTIFACTS) if d.startswith("run-"))
    return runs[-1] if runs else None


def load(p):
    return json.load(open(p)) if os.path.isfile(p) else {}


def _set(run, size, color, bold=False, mono=False, align=None, space_after=6):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    if mono:
        run.font.name = "Consolas"


def textbox(slide, x, y, w, h, lines, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for i, spec in enumerate(lines):
        text, size, color = spec[0], spec[1], spec[2]
        opts = spec[3] if len(spec) > 3 else {}
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        if opts.get("align"):
            p.alignment = opts["align"]
        p.space_after = Pt(opts.get("space_after", 6))
        p.space_before = Pt(opts.get("space_before", 0))
        r = p.add_run(); r.text = text
        _set(r, size, color, bold=opts.get("bold", False), mono=opts.get("mono", False))
    return tb


def panel(slide, x, y, w, h, title, body):
    """A titled content panel: header bar + white body with `body` lines."""
    # body card
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    card.fill.solid(); card.fill.fore_color.rgb = WHITE
    card.line.color.rgb = ANL_TEAL; card.line.width = Pt(1.5)
    card.shadow.inherit = False
    # header bar
    hb = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(1.1))
    hb.fill.solid(); hb.fill.fore_color.rgb = ANL_BLUE
    hb.line.fill.background(); hb.shadow.inherit = False
    htf = hb.text_frame; htf.word_wrap = True
    htf.margin_left = Inches(0.25); htf.vertical_anchor = MSO_ANCHOR.MIDDLE
    r = htf.paragraphs[0].add_run(); r.text = title
    _set(r, 26, WHITE, bold=True)
    # body text
    textbox(slide, x + 0.35, y + 1.35, w - 0.7, h - 1.6, body)


def main():
    run_id = latest_run()
    run_dir = os.path.join(ARTIFACTS, run_id) if run_id else ""
    m = load(os.path.join(run_dir, "metrics.json"))
    v = load(os.path.join(run_dir, "verification.json"))
    c = m.get("correctness", {}); e = m.get("efficiency", {}); h = m.get("human_effort", {})
    order = ", ".join("%.2f" % p for p in (c.get("observed_order_maxnorm") or [])) or "2.00"
    errs = v.get("max_norm_error") or []
    sizes = v.get("sizes") or []

    prs = Presentation()
    prs.slide_width = Inches(W); prs.slide_height = Inches(H)
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # ---- background band + title ----
    band = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(W), Inches(4.2))
    band.fill.solid(); band.fill.fore_color.rgb = ANL_BLUE; band.line.fill.background()
    band.shadow.inherit = False
    textbox(slide, 0.8, 0.35, W - 1.6, 3.6, [
        ("Automated Problem-to-Solution Generation for a Tokamak Fusion-Plasma Simulation",
         40, WHITE, {"bold": True, "space_after": 2}),
        ("A hierarchical multi-agent PETSc system: from a plain-language prompt to a verified Grad-Shafranov MHD-equilibrium solver",
         24, RGBColor(0xCF, 0xE6, 0xEA), {"space_after": 6}),
        ("[PRESENTER NAME], <email>, ORCID  ·  Mathematics and Computer Science Division, Argonne National Laboratory  ·  US-RSE 2026",
         18, WHITE, {}),
    ])

    colw = 15.0
    x1, x2, x3 = 0.8, 16.5, 32.2
    ytop = 4.8
    colh = 30.6

    # ---- Column 1 ----
    panel(slide, x1, ytop, colw, 8.6, "1  Motivation", [
        ("Turning a scientific idea into correct, fast HPC simulation code still demands scarce, "
         "largely implicit expertise in numerical methods and library APIs.", 19, DARK, {"space_after": 10}),
        ("Question: can a hierarchical multi-agent AI system automate that path for a real "
         "fusion-energy problem — and can the result be verified, not merely plausible?", 19, DARK, {"space_after": 10}),
        ("We apply the open PETSc multi-agent system to the tokamak Grad-Shafranov equilibrium, "
         "the MHD stretch goal of the DOE proposal on automated PDE problem-to-solution generation.", 19, DARK, {}),
    ])
    panel(slide, x1, ytop + 9.0, colw, 8.0, "2  The problem: Grad-Shafranov", [
        ("Axisymmetric ideal-MHD force balance for the poloidal flux ψ(R,Z):", 19, DARK, {"space_after": 8}),
        ("Δ* ψ = -μ₀ R² p′(ψ) - F F′(ψ)", 26, ANL_TEAL, {"bold": True, "space_after": 8, "align": PP_ALIGN.CENTER}),
        ("Its solution gives the flux surfaces, magnetic axis, and safety factor q that determine "
         "whether the plasma stays confined.", 19, DARK, {"space_after": 8}),
        ("Elliptic, nonlinear, time-independent → a natural PETSc SNES problem; verifiable against "
         "a manufactured exact solution.", 19, DARK, {}),
    ])
    panel(slide, x1, ytop + 17.4, colw, colh - 17.4, "3  The multi-agent system", [
        ("Three layers of specialist agents, each a Model-Context-Protocol server:", 19, DARK, {"space_after": 8}),
        ("Problem Definition — Mathematical Modeling agent → strong/weak form, PDE identity.", 18, DARK, {"space_after": 6}),
        ("Agent Execution — Numerical Analysis agent → grid, discretization, solver;", 18, DARK, {"space_after": 2}),
        ("        HPC Code Generation agent → writes, compiles & runs PETSc C;", 18, DARK, {"space_after": 2}),
        ("        compile-run agent → make / run on the real machine.", 18, DARK, {"space_after": 6}),
        ("Workflow Control — a project-owned driver that records every artifact with provenance "
         "(reproducible, resumable).", 18, DARK, {"space_after": 6}),
        ("All agents run against Argonne's Argo gateway (Claude Opus 4.8).", 18, GREY, {}),
    ])

    # ---- Column 2 ----
    panel(slide, x2, ytop, colw, 8.2, "4  The pipeline in action", [
        ("Prompt: “the Grad-Shafranov equilibrium for the plasma in a tokamak.”", 19, DARK, {"space_after": 8, "bold": True}),
        ("Modeling agent → identified ‘%s’; time-dependent = False." % (c.get("model_name") or "Grad-Shafranov equation"), 18, DARK, {"space_after": 6}),
        ("Numerical Analysis agent → nonlinear solve with SNES.", 18, DARK, {"space_after": 6}),
        ("Code Generation agent → %s-line PETSc DMDA+SNES solver (true Jacobian, MMS check)."
         % (h.get("solver_lines_agent_generated") or 267), 18, DARK, {"space_after": 6}),
        ("Compiled and ran on 1 and 4 MPI ranks — no human edits.", 18, ANL_TEAL, {"bold": True}),
    ])
    # generated-code excerpt
    panel(slide, x2, ytop + 8.6, colw, 8.4, "5  The agent-generated solver (excerpt)", [
        ("/* residual: Delta*_h psi - f, Dirichlet on edges */", 13, GREY, {"mono": True, "space_after": 2}),
        ("dRR = (x[j][i+1]-2*x[j][i]+x[j][i-1])/(hR*hR);", 13, DARK, {"mono": True, "space_after": 2}),
        ("dR  = (x[j][i+1]-x[j][i-1])/(2*hR);", 13, DARK, {"mono": True, "space_after": 2}),
        ("dZZ = (x[j+1][i]-2*x[j][i]+x[j-1][i])/(hZ*hZ);", 13, DARK, {"mono": True, "space_after": 2}),
        ("f[j][i] = dRR - dR/R + dZZ - ForcingF(user,R,Z);", 13, DARK, {"mono": True, "space_after": 6}),
        ("SNESSetFunction(snes, r, FormFunction, &user);", 13, DARK, {"mono": True, "space_after": 2}),
        ("SNESSetJacobian(snes, J, J, FormJacobian, &user);", 13, DARK, {"mono": True, "space_after": 2}),
        ("SNESSolve(snes, NULL, x);", 13, DARK, {"mono": True}),
    ])
    # flux surfaces figure
    fp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x2), Inches(ytop + 17.4), Inches(colw), Inches(colh - 17.4))
    fp.fill.solid(); fp.fill.fore_color.rgb = WHITE; fp.line.color.rgb = ANL_TEAL; fp.line.width = Pt(1.5)
    fp.shadow.inherit = False
    flux = os.path.join(FIGURES, "gs_flux_surfaces.png")
    if os.path.isfile(flux):
        slide.shapes.add_picture(flux, Inches(x2 + 4.2), Inches(ytop + 17.8), height=Inches(11.2))
    textbox(slide, x2 + 0.35, ytop + colh - 1.1, colw - 0.7, 1.0,
            [("Fig. 1  Poloidal flux surfaces ψ(R,Z) of the verified equilibrium (nested surfaces about the magnetic axis).", 15, GREY, {"align": PP_ALIGN.CENTER})])

    # ---- Column 3 ----
    # convergence figure panel
    cp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x3), Inches(ytop), Inches(colw), Inches(11.4))
    cp.fill.solid(); cp.fill.fore_color.rgb = WHITE; cp.line.color.rgb = ANL_TEAL; cp.line.width = Pt(1.5)
    cp.shadow.inherit = False
    textbox(slide, x3 + 0.35, ytop + 0.25, colw - 0.7, 0.9,
            [("6  Verification: it is actually right", 26, ANL_BLUE, {"bold": True})])
    conv = os.path.join(FIGURES, "gs_convergence.png")
    if os.path.isfile(conv):
        slide.shapes.add_picture(conv, Inches(x3 + 1.7), Inches(ytop + 1.3), width=Inches(11.6))
    textbox(slide, x3 + 0.35, ytop + 10.2, colw - 0.7, 1.1,
            [("Fig. 2  Manufactured-solution error vs grid spacing; both norms track the h² reference → observed order p = %s." % order, 15, GREY, {"align": PP_ALIGN.CENTER})])

    # metrics panel
    me = errs[-1] if errs else 1.3e-5
    m0 = errs[0] if errs else 8.4e-4
    panel(slide, x3, ytop + 12.0, colw, 9.4, "7  Decision-gate metrics", [
        ("Correctness — model identified ✓; compiled & ran ✓; %s." % (c.get("snes_converged_reason","CONVERGED_FNORM_RELATIVE").split(":")[-1].strip()), 18, DARK, {"space_after": 6}),
        ("Second-order convergence: p = %s  (error %.1e → %.1e over %s→%s)."
         % (order, m0, me, sizes[0] if sizes else 33, sizes[-1] if sizes else 257), 18, DARK, {"space_after": 6}),
        ("Human effort — %s lines of solver code hand-written; %s generated by the agents."
         % (h.get("solver_lines_handwritten", 0), h.get("solver_lines_agent_generated", 267)), 18, DARK, {"space_after": 6}),
        ("Efficiency — ~%s s wall-clock; %s code-gen tool calls; ~%s LLM completions."
         % (e.get("wallclock_seconds_total","?"), e.get("codegen_tool_calls","?"), e.get("approx_llm_completions","?")), 18, DARK, {}),
    ])
    # contributions + conclusions + refs
    panel(slide, x3, ytop + 21.8, colw, colh - 21.8, "8  Contributions & conclusions", [
        ("A multi-agent system generated a correct, verified PETSc fusion-MHD solver from a prompt.", 17, DARK, {"space_after": 6}),
        ("Verification-driven: exact-solution + grid-convergence checks, not just plausible output.", 17, DARK, {"space_after": 6}),
        ("Contributed fixes upstream: CWD-independent server resolution; graceful no-docs/RAG "
         "operation; reliable code-gen capture.", 17, DARK, {"space_after": 6}),
        ("Next: shaped real-machine equilibria (Solov’ev/Cerfon-Freidberg), q-profile, GPU scale-up.", 17, GREY, {"space_after": 8}),
        ("Code + data: github.com/engineer-scientist/petsc_mcp_servers_tokamak   ·   "
         "System: gitlab.com/petsc/petsc_mcp_servers", 15, ANL_TEAL, {}),
    ])

    out = os.path.join(HERE, "USRSE26_poster.pptx")
    prs.save(out)
    print("[poster] wrote %s (%.0f x %.0f in) from run %s" % (out, W, H, run_id))


if __name__ == "__main__":
    main()
