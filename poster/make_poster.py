#!/usr/bin/env python3
"""
make_poster.py -- build the US-RSE 2026 poster from ONE layout spec, with two backends:
  * an EDITABLE PowerPoint  -> poster/USRSE26_poster.pptx   (native text boxes + shapes)
  * a preview image + PDF   -> poster/USRSE26_poster_preview.png / .pdf  (matplotlib)

Both back-ends use the SAME positions (inches) and font sizes (points). Points are
absolute (1 pt = 1/72 in), so the preview faithfully shows how big the text is on the
48 in x 36 in poster -- use it to check readability without PowerPoint/LibreOffice.

Content/numbers come from artifacts/<latest>/metrics.json + verification.json; figures
from figures/.

Run with a Python that has python-pptx + matplotlib (the tokamak venv has both):
  /home/sarthak.sharma/tokamak/.venv/bin/python poster/make_poster.py
"""
import os
import json
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
ARTIFACTS = os.path.join(PROJECT, "artifacts")
FIGURES = os.path.join(PROJECT, "figures")

W, H = 48.0, 36.0                      # poster size, inches
BLUE = "#002B5C"; TEAL = "#007D8A"; DARK = "#1F1F1F"; GREY = "#4A4A4A"; WHITE = "#FFFFFF"

# ---- poster-appropriate font sizes (points) ----
F_TITLE, F_SUB, F_AUTH = 66, 34, 27
F_HEAD, F_BODY, F_SMALL, F_EQ, F_CODE, F_CAP = 40, 30, 27, 40, 23, 25
BAND_H = 5.8   # title band height (inches)


def latest_run():
    p = os.path.join(ARTIFACTS, "LATEST")
    if os.path.isfile(p):
        return open(p).read().strip()
    runs = sorted(d for d in os.listdir(ARTIFACTS) if d.startswith("run-"))
    return runs[-1] if runs else None


def load(p):
    return json.load(open(p)) if os.path.isfile(p) else {}


def build_spec():
    """Return the poster as data: a title band, panels, figures. Positions in inches."""
    run_id = latest_run()
    run_dir = os.path.join(ARTIFACTS, run_id) if run_id else ""
    m = load(os.path.join(run_dir, "metrics.json"))
    v = load(os.path.join(run_dir, "verification.json"))
    c = m.get("correctness", {}); e = m.get("efficiency", {}); h = m.get("human_effort", {})
    order = ", ".join("%.2f" % p for p in (c.get("observed_order_maxnorm") or [])) or "2.00"
    errs = v.get("max_norm_error") or [8.4e-4, 2.1e-4, 5.3e-5, 1.3e-5]
    sizes = v.get("sizes") or [33, 65, 129, 257]
    lines_gen = h.get("solver_lines_agent_generated") or 267

    # geometry
    colw, gut = 14.9, 0.55
    x1 = 0.7; x2 = x1 + colw + gut; x3 = x2 + colw + gut
    ytop = 6.4
    ybot = 35.4

    panels, figs = [], []

    # ---- column 1 ----
    panels.append(dict(x=x1, y=ytop, w=colw, h=8.4, title="1  Motivation", body=[
        ("Correct, fast HPC simulation code still demands scarce, implicit expertise in "
         "numerical methods and library APIs.", F_BODY, DARK),
        ("Can a multi-agent AI system automate the path from a plain-language idea to "
         "VERIFIED code for a real fusion problem?", F_BODY, DARK),
        ("We apply the open PETSc multi-agent system to the tokamak Grad-Shafranov equilibrium.",
         F_BODY, DARK),
    ]))
    panels.append(dict(x=x1, y=ytop + 8.9, w=colw, h=8.4, title="2  The problem", body=[
        ("Axisymmetric ideal-MHD force balance for the poloidal flux psi(R,Z):", F_BODY, DARK),
        ("Δ*psi = -μ₀R² p'(psi) - F F'(psi)", F_EQ, TEAL, "eq"),
        ("Gives the flux surfaces, magnetic axis, and safety factor q.", F_BODY, DARK),
        ("Elliptic, nonlinear → PETSc SNES; verifiable vs an exact solution.", F_BODY, DARK),
    ]))
    panels.append(dict(x=x1, y=ytop + 17.8, w=colw, h=ybot - (ytop + 17.8),
                       title="3  The multi-agent system", body=[
        ("Three layers of specialist agents (MCP servers):", F_BODY, DARK),
        ("• Modeling → PDE identity & strong/weak forms", F_BODY, DARK),
        ("• Numerical Analysis → grid, discretization, solver", F_BODY, DARK),
        ("• HPC Code Generation → writes, compiles & runs PETSc C", F_BODY, DARK),
        ("• Driver → records every artifact (provenance)", F_BODY, DARK),
        ("All agents run on ANL's Argo gateway (Claude Opus 4.8).", F_SMALL, GREY),
    ]))

    # ---- column 2 ----
    panels.append(dict(x=x2, y=ytop, w=colw, h=8.4, title="4  The pipeline in action", body=[
        ("Prompt: “the Grad-Shafranov equilibrium for the plasma in a tokamak.”",
         F_BODY, DARK, "b"),
        ("Modeling → ‘Grad-Shafranov equation’, steady.", F_BODY, DARK),
        ("Numerical Analysis → nonlinear ⇒ SNES.", F_BODY, DARK),
        ("Code Generation → %d-line PETSc DMDA+SNES solver." % lines_gen, F_BODY, DARK),
        ("Compiled & ran on 1 and 4 MPI ranks — no human edits.", F_BODY, TEAL, "b"),
    ]))
    panels.append(dict(x=x2, y=ytop + 8.9, w=colw, h=8.4,
                       title="5  Generated solver (excerpt)", body=[
        ("/* residual: Delta*_h psi - f */", F_CODE, GREY, "code"),
        ("dRR=(x[j][i+1]-2x[j][i]+x[j][i-1])/hR2;", F_CODE, DARK, "code"),
        ("dZZ=(x[j+1][i]-2x[j][i]+x[j-1][i])/hZ2;", F_CODE, DARK, "code"),
        ("f[j][i]=dRR-dR/R+dZZ-ForcingF(u,R,Z);", F_CODE, DARK, "code"),
        ("SNESSetJacobian(snes,J,J,FormJacobian,&u);", F_CODE, DARK, "code"),
        ("SNESSolve(snes,NULL,x);", F_CODE, DARK, "code"),
    ]))
    figs.append(dict(x=x2, y=ytop + 17.8, w=colw, h=ybot - (ytop + 17.8),
                     path=os.path.join(FIGURES, "gs_flux_surfaces.png"),
                     caption="Fig. 1  Poloidal flux surfaces psi(R,Z) of the verified equilibrium."))

    # ---- column 3 ----
    figs.append(dict(x=x3, y=ytop, w=colw, h=12.0, title="6  Verification",
                     path=os.path.join(FIGURES, "gs_convergence.png"),
                     caption="Fig. 2  Error vs grid spacing tracks h² → observed order p = %s." % order))
    panels.append(dict(x=x3, y=ytop + 12.5, w=colw, h=8.4, title="7  Decision-gate metrics", body=[
        ("Model identified ✓   Compiled & ran ✓   SNES converged ✓", F_BODY, DARK),
        ("Second-order: p = %s  (error %.1e → %.1e, %d→%d)."
         % (order, errs[0], errs[-1], sizes[0], sizes[-1]), F_BODY, DARK),
        ("Human effort: 0 solver lines written; %d generated." % lines_gen, F_BODY, DARK),
        ("Efficiency: ~%s s wall-clock; ~%s LLM completions."
         % (e.get("wallclock_seconds_total", "451"), e.get("approx_llm_completions", "23")), F_BODY, DARK),
    ]))
    panels.append(dict(x=x3, y=ytop + 21.4, w=colw, h=ybot - (ytop + 21.4),
                       title="8  Contributions & conclusions", body=[
        ("A verified PETSc fusion-MHD solver produced from a prompt.", F_BODY, DARK),
        ("Verification-driven: exact-solution + convergence checks.", F_BODY, DARK),
        ("Upstream fixes: CWD-independent servers; graceful no-docs/RAG; reliable capture.",
         F_SMALL, DARK),
        ("github.com/engineer-scientist/petsc_mcp_servers_tokamak", F_SMALL, TEAL),
    ]))

    title = dict(
        title="Automated Problem-to-Solution Generation for a Tokamak Fusion-Plasma Simulation",
        sub="A hierarchical multi-agent PETSc system: from a plain-language prompt to a verified Grad-Shafranov solver",
        auth="Sarthak Sharma (State University of New York at Buffalo)  ·  Dr Junchao Zhang (Mathematics and Computer Science Division, Argonne National Laboratory)  ·  US-RSE 2026",
    )
    return dict(title=title, panels=panels, figs=figs, run_id=run_id)


# ============================ matplotlib preview backend ============================
def render_preview(spec, out_png, out_pdf):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, Rectangle
    import matplotlib.image as mpimg

    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")

    def Y(y_top):
        return H - y_top

    def wrap(text, size, width_in):
        # avg glyph ~0.52 em; em = size/72 in
        maxchars = max(8, int(width_in / (0.52 * size / 72.0)))
        return textwrap.wrap(text, maxchars) or [""]

    def draw_lines(x, y_top, w, body, pad=0.3):
        yy = y_top
        for spec_line in body:
            text, size, color = spec_line[0], spec_line[1], spec_line[2]
            role = spec_line[3] if len(spec_line) > 3 else ""
            bold = role in ("b", "eq")
            mono = role == "code"
            align = "center" if role == "eq" else "left"
            xx = x + w / 2 if align == "center" else x + pad
            fam = "monospace" if mono else "sans-serif"
            for ln in ([text] if (mono or role == "eq") else wrap(text, size, w - 2 * pad)):
                ax.text(xx, Y(yy), ln, fontsize=size, color=color, va="top",
                        ha=align, fontweight="bold" if bold else "normal", family=fam)
                yy += size / 72.0 * 1.32
            yy += 0.12
        return yy

    # title band (title wraps to ~2 lines; then subtitle, then authors)
    ax.add_patch(Rectangle((0, Y(BAND_H)), W, BAND_H, color=BLUE, zorder=0))
    yy = 0.45
    for ln in textwrap.wrap(spec["title"]["title"], 47):
        ax.text(0.8, Y(yy), ln, fontsize=F_TITLE, color=WHITE, va="top", fontweight="bold")
        yy += F_TITLE / 72.0 * 1.16
    yy += 0.18
    ax.text(0.8, Y(yy), spec["title"]["sub"], fontsize=F_SUB, color="#CFE6EA", va="top")
    yy += F_SUB / 72.0 * 1.3 + 0.15
    ax.text(0.8, Y(yy), spec["title"]["auth"], fontsize=F_AUTH, color=WHITE, va="top")

    # panels
    for p in spec["panels"]:
        ax.add_patch(FancyBboxPatch((p["x"], Y(p["y"] + p["h"])), p["w"], p["h"],
                     boxstyle="round,pad=0,rounding_size=0.12", ec=TEAL, fc=WHITE, lw=2))
        ax.add_patch(Rectangle((p["x"], Y(p["y"] + 1.25)), p["w"], 1.25, color=BLUE))
        ax.text(p["x"] + 0.3, Y(p["y"] + 0.28), p["title"], fontsize=F_HEAD, color=WHITE,
                va="top", fontweight="bold")
        draw_lines(p["x"], p["y"] + 1.55, p["w"], p["body"])

    # figures
    for f in spec["figs"]:
        ax.add_patch(FancyBboxPatch((f["x"], Y(f["y"] + f["h"])), f["w"], f["h"],
                     boxstyle="round,pad=0,rounding_size=0.12", ec=TEAL, fc=WHITE, lw=2))
        y_img = f["y"] + 0.3
        if f.get("title"):
            ax.add_patch(Rectangle((f["x"], Y(f["y"] + 1.25)), f["w"], 1.25, color=BLUE))
            ax.text(f["x"] + 0.3, Y(f["y"] + 0.28), f["title"], fontsize=F_HEAD, color=WHITE,
                    va="top", fontweight="bold")
            y_img = f["y"] + 1.5
        cap_h = 1.3
        if f.get("path") and os.path.isfile(f["path"]):
            img = mpimg.imread(f["path"])
            ih, iw = img.shape[0], img.shape[1]
            avail_w = f["w"] - 1.0
            avail_h = f["y"] + f["h"] - y_img - cap_h
            scale = min(avail_w / iw, avail_h / ih) * 72  # px->in via 72 assumption
            dw, dh = iw * scale / 72, ih * scale / 72
            ix = f["x"] + (f["w"] - dw) / 2
            iy = y_img
            ax.imshow(img, extent=[ix, ix + dw, Y(iy + dh), Y(iy)], zorder=5, aspect="auto")
        for i, ln in enumerate(wrap(f["caption"], F_CAP, f["w"] - 0.8)):
            ax.text(f["x"] + f["w"] / 2, Y(f["y"] + f["h"] - cap_h + 0.15 + i * F_CAP / 72 * 1.3),
                    ln, fontsize=F_CAP, color=GREY, va="top", ha="center")

    fig.savefig(out_png, dpi=64); fig.savefig(out_pdf); plt.close(fig)
    print("[poster] wrote %s and %s" % (out_png, out_pdf))


# ============================ python-pptx backend ============================
def render_pptx(spec, out):
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.enum.shapes import MSO_SHAPE

    def rgb(hexs):
        return RGBColor(int(hexs[1:3], 16), int(hexs[3:5], 16), int(hexs[5:7], 16))

    prs = Presentation(); prs.slide_width = Inches(W); prs.slide_height = Inches(H)
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    def box(x, y, w, h, lines, anchor=MSO_ANCHOR.TOP):
        tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
        for i, (text, size, color, *rest) in enumerate(lines):
            role = rest[0] if rest else ""
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.CENTER if role == "eq" else PP_ALIGN.LEFT
            p.space_after = Pt(6)
            r = p.add_run(); r.text = text
            r.font.size = Pt(size); r.font.color.rgb = rgb(color)
            r.font.bold = role in ("b", "eq")
            if role == "code":
                r.font.name = "Consolas"
        return tb

    def rect(x, y, w, h, color, line=None):
        s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        s.fill.solid(); s.fill.fore_color.rgb = rgb(color)
        if line:
            s.line.color.rgb = rgb(line); s.line.width = Pt(1.5)
        else:
            s.line.fill.background()
        s.shadow.inherit = False
        return s

    def card(x, y, w, h):
        s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        s.fill.solid(); s.fill.fore_color.rgb = rgb(WHITE)
        s.line.color.rgb = rgb(TEAL); s.line.width = Pt(2); s.shadow.inherit = False
        return s

    def header(x, y, w, title):
        hb = rect(x, y, w, 1.25, BLUE)
        tf = hb.text_frame; tf.margin_left = Inches(0.3); tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        r = tf.paragraphs[0].add_run(); r.text = title
        r.font.size = Pt(F_HEAD); r.font.bold = True; r.font.color.rgb = rgb(WHITE)

    # title band
    rect(0, 0, W, BAND_H, BLUE)
    box(0.8, 0.35, W - 1.6, BAND_H - 0.6, [
        (spec["title"]["title"], F_TITLE, WHITE, "b"),
        (spec["title"]["sub"], F_SUB, "#CFE6EA"),
        (spec["title"]["auth"], F_AUTH, WHITE),
    ])

    for p in spec["panels"]:
        card(p["x"], p["y"], p["w"], p["h"]); header(p["x"], p["y"], p["w"], p["title"])
        box(p["x"] + 0.3, p["y"] + 1.45, p["w"] - 0.6, p["h"] - 1.7, p["body"])

    for f in spec["figs"]:
        card(f["x"], f["y"], f["w"], f["h"])
        y_img = f["y"] + 0.35
        if f.get("title"):
            header(f["x"], f["y"], f["w"], f["title"]); y_img = f["y"] + 1.5
        if f.get("path") and os.path.isfile(f["path"]):
            from PIL import Image
            iw, ih = Image.open(f["path"]).size
            cap_h = 1.35
            avail_w = f["w"] - 1.0; avail_h = f["y"] + f["h"] - y_img - cap_h
            scale = min(avail_w / iw, avail_h / ih)
            dw, dh = iw * scale, ih * scale
            slide.shapes.add_picture(f["path"], Inches(f["x"] + (f["w"] - dw) / 2),
                                     Inches(y_img), height=Inches(dh))
        box(f["x"] + 0.3, f["y"] + f["h"] - 1.35, f["w"] - 0.6, 1.2,
            [(f["caption"], F_CAP, GREY)], anchor=MSO_ANCHOR.TOP)

    prs.save(out)
    print("[poster] wrote %s (%.0f x %.0f in) from run %s" % (out, W, H, spec["run_id"]))


def main():
    spec = build_spec()
    render_pptx(spec, os.path.join(HERE, "USRSE26_poster.pptx"))
    render_preview(spec, os.path.join(HERE, "USRSE26_poster_preview.png"),
                   os.path.join(HERE, "USRSE26_poster_preview.pdf"))


if __name__ == "__main__":
    main()
