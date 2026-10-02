"""Plot helpers for Phase 1 visual checks (no analysis)."""
import matplotlib.pyplot as plt
from mplsoccer import Pitch

from .load import get_frame, load_meta

HOME = "#2a78d6"   # categorical slot 1
AWAY = "#eb6834"   # categorical slot 2
INK = "#2b2b2b"
MUTED = "#8a8a85"


def plot_frame(match_id, frame_id, ax=None):
    """Draw one frame in raw-orientation metres (x_m, y_m; +y up).

    Detected players: filled circle. Extrapolated (SkillCorner) players: hollow ring, dashed edge.
    Ball: small black dot (hollow if not detected). Arrow: direction the HOME team attacks.
    """
    meta = load_meta(match_id)
    L, W = meta["pitch_length_m"], meta["pitch_width_m"]
    f = get_frame(match_id, frame_id)
    pitch = Pitch(pitch_type="custom", pitch_length=L, pitch_width=W, line_color="#b9b9b3",
                  pitch_color="white", linewidth=1)
    if ax is None:
        fig, ax = plt.subplots(figsize=(7, 4.8))
    pitch.draw(ax=ax)
    # mplsoccer 'custom' pitch has its origin at the bottom-left corner: shift centre origin
    ox, oy = L / 2, W / 2
    pl = f[f.object_type == "player"]
    for side, col in (("home", HOME), ("away", AWAY)):
        t = pl[pl.team_side == side]
        det = t[t.is_detected == True]
        ext = t[(t.is_detected == False) & t.x_m.notna()]
        ax.scatter(det.x_m + ox, det.y_m + oy, s=90, c=col, edgecolors="white", linewidths=1.5, zorder=3,
                   label=f"{side} detected")
        ax.scatter(ext.x_m + ox, ext.y_m + oy, s=90, facecolors="white", edgecolors=col, linewidths=1.8,
                   linestyle="--", zorder=3, label=f"{side} extrapolated")
        for r in t[t.x_m.notna()].itertuples():
            if r.jersey_number is not None and r.jersey_number == r.jersey_number:
                ax.text(r.x_m + ox, r.y_m + oy - 2.3, str(int(r.jersey_number)), fontsize=6,
                        ha="center", va="top", color=INK, zorder=4)
    b = f[f.object_type == "ball"].iloc[0]
    if b.x_m == b.x_m:
        detected = bool(b.is_detected) if b.is_detected is not None and b.is_detected == b.is_detected else False
        ax.scatter(b.x_m + ox, b.y_m + oy, s=35, c=INK if detected else "white", edgecolors=INK,
                   linewidths=1.2, zorder=5, label="ball")
    home_plus = meta["attack_direction"][str(int(f.period.iloc[0]))]["home_attacks_plus_x"]
    x0, x1 = (-12, 12) if home_plus else (12, -12)
    ax.annotate("", xy=(ox + x1, W + 3), xytext=(ox + x0, W + 3),
                arrowprops=dict(arrowstyle="-|>", color=HOME, lw=2), annotation_clip=False)
    ax.text(ox + 15, W + 3, "home attacks", color=INK, ha="left", va="center", fontsize=8)
    poss = f.possession_group.dropna()
    poss = poss.iloc[0] if len(poss) else "none/unknown"
    n_det = int((pl.is_detected == True).sum()); n_pos = int(pl.x_m.notna().sum())
    ax.set_title(f"{match_id}  P{int(f.period.iloc[0])}  frame {frame_id}  t={f.timestamp_s.iloc[0]:.1f}s\n"
                 f"possession: {poss}   players with position: {n_pos} (detected {n_det})",
                 fontsize=8, color=INK, pad=22)
    return ax


def legend_handles():
    from matplotlib.lines import Line2D
    mk = lambda **kw: Line2D([], [], marker="o", linestyle="none", markersize=9, **kw)
    return [mk(markerfacecolor=HOME, markeredgecolor="white", label="home - detected"),
            mk(markerfacecolor="white", markeredgecolor=HOME, markeredgewidth=1.8, label="home - extrapolated"),
            mk(markerfacecolor=AWAY, markeredgecolor="white", label="away - detected"),
            mk(markerfacecolor="white", markeredgecolor=AWAY, markeredgewidth=1.8, label="away - extrapolated"),
            Line2D([], [], marker="o", linestyle="none", markersize=6, markerfacecolor=INK, markeredgecolor=INK, label="ball - detected"),
            Line2D([], [], marker="o", linestyle="none", markersize=6, markerfacecolor="white", markeredgecolor=INK, label="ball - not detected"),
            Line2D([], [], color=HOME, lw=2, marker=">", label="direction home attacks (this period)")]
