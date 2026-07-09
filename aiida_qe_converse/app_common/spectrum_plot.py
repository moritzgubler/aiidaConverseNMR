"""Shared spectrum-plot helpers for the EFG results panel and the standalone
quadrupolar simulator app.

Imports only numpy/plotly/IPython -- no aiida, aiidalab_qe or
aiidalab_widgets_base, so this module stays importable in a bare Jupyter
environment (the standalone AiiDAlab app depends on that).

Every trace style, CSV column name and layout choice for the quadrupolar
spectrum lives here so the two GUIs cannot drift apart.
"""

import numpy as np

# qualitative palette for the per-transition powder curves
TRANSITION_COLORS = ["#17becf", "#9467bd", "#2ca02c", "#ff7f0e",
                     "#e377c2", "#8c564b", "#bcbd22", "#1f77b4", "#d62728"]

# the spectrum frequency axis (nu - nu_L) is plotted in kHz
MHZ_TO_KHZ = 1000.0


def half_int_str(x):
    """Format a multiple of 1/2 as a tidy string: 0.5->'1/2', -1.5->'−3/2', 1->'1'."""
    n = int(round(2 * x))
    s = str(n // 2) if n % 2 == 0 else f"{n}/2"
    return s.replace("-", "−")


def transition_ascii(m):
    """ASCII transition label for CSV export, e.g. '-1/2<->1/2'."""
    return f"{half_int_str(m - 1)}<->{half_int_str(m)}".replace("−", "-")


def add_stick_traces(fig, lines, nu_L):
    """Draw labelled transition sticks (height = relative weight) on ``fig``."""
    import plotly.graph_objects as go

    wmax = max((w for _, w, _ in lines), default=1.0) or 1.0
    for freq, weight, m in lines:
        x0 = (freq - nu_L) * MHZ_TO_KHZ
        height = weight / wmax
        label = f"{half_int_str(m - 1)}↔{half_int_str(m)}"
        fig.add_trace(go.Scatter(
            x=[x0, x0], y=[0.0, height], mode="lines",
            line=dict(color="#d62728", width=2), showlegend=False,
            hoverinfo="text", hovertext=f"{label}  (Δν = {x0:.2f} kHz)"))
        fig.add_trace(go.Scatter(
            x=[x0], y=[height], mode="markers+text",
            marker=dict(color="#d62728", size=4),
            text=[label], textposition="top center",
            textfont=dict(size=10, color="#d62728"),
            showlegend=False, hoverinfo="skip"))
    fig.update_yaxes(range=[0.0, 1.2])  # headroom for the labels


def stick_block(title, lines, nu_L):
    """Export block mirroring ``add_stick_traces`` (intensity_norm = plotted height)."""
    wmax = max((w for _, w, _ in lines), default=1.0) or 1.0
    return (title,
            ["nu_minus_nuL_kHz", "nu_MHz", "weight", "intensity_norm", "transition"],
            [[(f - nu_L) * MHZ_TO_KHZ for f, _, _ in lines],
             [f for f, _, _ in lines],
             [w for _, w, _ in lines],
             [w / wmax for _, w, _ in lines],
             [transition_ascii(m) for _, _, m in lines]])


def add_powder_traces(fig, freqs, total, per_transition, nu_L):
    """Powder lineshape traces: total + optional per-transition decomposition.

    ``per_transition`` is the ``[(m, intensity), ...]`` list from
    ``powder_spectrum_by_transition`` (thesis Fig. 2.3 style), or None for
    just the total. Returns ``(export_block, show_legend)`` mirroring the
    drawn traces.
    """
    import plotly.graph_objects as go

    x = (freqs - nu_L) * MHZ_TO_KHZ
    if per_transition is None:
        fig.add_trace(go.Scatter(x=x, y=total, mode="lines",
                                 line=dict(color="#1f77b4")))
        return (("powder lineshape",
                 ["nu_minus_nuL_kHz", "nu_MHz", "intensity_total"],
                 [x, freqs, total]), False)
    fig.add_trace(go.Scatter(x=x, y=total, mode="lines", name="total",
                             line=dict(color="#000000", width=2)))
    names = ["nu_minus_nuL_kHz", "nu_MHz", "intensity_total"]
    cols = [x, freqs, total]
    for i, (m, inten) in enumerate(per_transition):
        lbl = f"{half_int_str(m - 1)}↔{half_int_str(m)}"
        fig.add_trace(go.Scatter(
            x=x, y=inten, mode="lines", name=lbl,
            line=dict(color=TRANSITION_COLORS[i % len(TRANSITION_COLORS)],
                      dash="dash")))
        names.append(f"intensity_{transition_ascii(m)}")
        cols.append(inten)
    return ("powder lineshape, decomposed by transition", names, cols), True


def add_envelope_trace(fig, gx, gy, nu_L):
    """Broadened single-crystal envelope trace; returns its export block."""
    import plotly.graph_objects as go

    x = (gx - nu_L) * MHZ_TO_KHZ
    fig.add_trace(go.Scatter(x=x, y=gy, mode="lines",
                             line=dict(color="#1f77b4")))
    return ("broadened envelope",
            ["nu_minus_nuL_kHz", "nu_MHz", "intensity"],
            [x, gx, gy])


def spectrum_layout(fig, show_legend):
    """The common axis/size/template styling of the spectrum figure."""
    fig.update_layout(
        xaxis_title="ν − ν_L (kHz)", yaxis_title="intensity (norm.)",
        height=420, margin=dict(l=50, r=20, t=20, b=50),
        template="plotly_white", showlegend=show_legend)


def direction_meta(direction, theta, phi):
    """Field-direction metadata lines for the CSV header."""
    da, db, dc = direction
    return [
        ("field_direction_abc", f"{da:g} {db:g} {dc:g}"),
        ("theta_deg", float(np.degrees(theta))),
        ("phi_deg", float(np.degrees(phi))),
    ]


def js_download_text(filename, text, mime):
    """Trigger a browser download of ``text`` via a JavaScript Blob."""
    import json
    from IPython.display import display, Javascript

    js_download = f"""
    var blob = new Blob([{json.dumps(text)}], {{type: '{mime}'}});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = '{filename}';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    """
    display(Javascript(js_download))
