"""Turn an Item into what a model receives: a text prompt (coordinates) or text + image.

Plan, Phase 4 factors: input format (coordinates table vs rendered image) x prompt style
(direct vs reason-then-answer). Controls: every prompt states pitch size, origin and the
attacking direction; rules are stated in the prompt; output is JSON {answer, confidence}.

No-leak rules (tested in tests/test_items.py):
* rows are ordered by team then shirt number, never by position;
* no margins, roles (e.g. goalkeeper), detection flags or derived quantities appear;
* the image shows the same scene as the table, at a fixed scale, with no title.

    from src.prompts import text_prompt, image_prompt, render_scene
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mplsoccer import Pitch

from .items import ATTACK, DEFEND, Item

STYLES = ("direct", "reason")
BLUE, ORANGE, INK, LINE = "#2a78d6", "#eb6834", "#1f1f1f", "#9a9a94"
IMG_SIZE_IN, IMG_DPI = (10.5, 7.2), 100          # fixed: every image is 1050 x 720 px


def _conventions(scene: dict) -> str:
    L, W = scene["pitch"]["length_m"], scene["pitch"]["width_m"]
    d = scene["attack_direction"]
    goal_x = f"+{L / 2:g}" if d == "+x" else f"-{L / 2:g}"
    return (f"Pitch: {L:g} m long (x axis) by {W:g} m wide (y axis). Origin (0, 0) is the centre spot; "
            f"x runs from -{L / 2:g} to +{L / 2:g} and y from -{W / 2:g} to +{W / 2:g}. Units are metres.\n"
            f"{ATTACK} is in possession and attacks towards {d}: {ATTACK} is trying to score in the goal "
            f"at x = {goal_x}. {DEFEND} defends that goal.")


def _table(scene: dict) -> str:
    rows = ["player | x | y"] + [f"{p['label']} | {p['x']:.2f} | {p['y']:.2f}" for p in scene["players"]]
    b = scene["ball"]
    rows.append(f"Ball | {b['x']:.2f} | {b['y']:.2f}")
    return "\n".join(rows)


def _options(item: Item) -> str:
    return "\n".join(f"{k}) {v}" for k, v in item.options.items())


def _output_instruction(style: str, letters) -> str:
    fmt = '{"answer": "<' + "|".join(letters) + '>", "confidence": <integer 0-100>}'
    if style == "direct":
        return f"Respond with only this JSON and nothing else:\n{fmt}"
    return ("Reason step by step. Then, on the final line, output only this JSON:\n" + fmt)


def _rules(item: Item) -> str:
    rule = item.provenance.get("rule_text")
    return f"\n\nRule: {rule}" if rule else ""


def text_prompt(item: Item, style: str = "direct") -> str:
    """Coordinates-table format."""
    if style not in STYLES:
        raise ValueError(f"style must be one of {STYLES}")
    s = item.scene
    return (f"You are given a snapshot of a football (soccer) match from tracking data.\n\n"
            f"{_conventions(s)}{_rules(item)}\n\n"
            f"Positions at this moment (each player is a single point):\n{_table(s)}\n\n"
            f"Question: {item.question}\n{_options(item)}\n\n"
            f"{_output_instruction(style, list(item.options))}")


def _zone_note(item: Item) -> str:
    if item.question_type != "overload_zone":
        return ""
    r = item.provenance.get("radius_m", 15.0)
    return f" The dashed circle marks the zone: {r:g} m around {item.provenance['carrier']}."


def image_prompt(item: Item, style: str = "direct") -> str:
    """Text that accompanies the rendered image (image format). No coordinates are given."""
    if style not in STYLES:
        raise ValueError(f"style must be one of {STYLES}")
    s = item.scene
    L, W = s["pitch"]["length_m"], s["pitch"]["width_m"]
    arrow = "right" if s["attack_direction"] == "+x" else "left"
    return (f"The image shows a snapshot of a football (soccer) match from tracking data, viewed from "
            f"above. The pitch is {L:g} m by {W:g} m. Blue dots are {ATTACK} players and orange dots are "
            f"{DEFEND} players, each labelled with a shirt number; the small black dot is the ball. "
            f"{ATTACK} is in possession and attacks towards the {arrow} (arrow above the pitch)."
            f"{_zone_note(item)}{_rules(item)}\n\n"
            f"Question: {item.question}\n{_options(item)}\n\n"
            f"{_output_instruction(style, list(item.options))}")


def render_scene(item: Item, path=None, dpi: int = IMG_DPI):
    """Render the item's scene at a fixed scale. Returns the matplotlib figure; saves PNG if path."""
    s = item.scene
    L, W = s["pitch"]["length_m"], s["pitch"]["width_m"]
    fig, ax = plt.subplots(figsize=IMG_SIZE_IN)
    Pitch(pitch_type="custom", pitch_length=L, pitch_width=W, line_color=LINE,
          pitch_color="white", linewidth=1.2).draw(ax=ax)
    ox, oy = L / 2, W / 2                      # mplsoccer 'custom' origin is the bottom-left corner
    for team, col in ((ATTACK, BLUE), (DEFEND, ORANGE)):
        ps = [p for p in s["players"] if p["team"] == team]
        ax.scatter([p["x"] + ox for p in ps], [p["y"] + oy for p in ps], s=170, c=col,
                   edgecolors="white", linewidths=1.5, zorder=3)
        for p in ps:
            ax.text(p["x"] + ox, p["y"] + oy, p["label"].split()[-1], color="white", fontsize=7,
                    ha="center", va="center", fontweight="bold", zorder=4)
    if s["ball"]:
        ax.scatter(s["ball"]["x"] + ox, s["ball"]["y"] + oy, s=45, c=INK, edgecolors="white",
                   linewidths=1, zorder=5)
    if item.question_type == "overload_zone":          # the zone is part of the question: draw it
        import matplotlib.patches as mpatches
        c = next(p for p in s["players"] if p["label"] == item.provenance["carrier"])
        ax.add_patch(mpatches.Circle((c["x"] + ox, c["y"] + oy), item.provenance.get("radius_m", 15.0),
                                     fill=False, ls="--", lw=1.5, ec=INK, zorder=2))
    x0, x1 = (ox - 10, ox + 10) if s["attack_direction"] == "+x" else (ox + 10, ox - 10)
    ax.annotate("", xy=(x1, W + 3), xytext=(x0, W + 3), annotation_clip=False,
                arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=2.5))
    ax.text(ox, W + 5.2, f"{ATTACK} attacks", color=BLUE, ha="center", fontsize=9, fontweight="bold")
    ax.set_xlim(-3, L + 3); ax.set_ylim(-3, W + 7)
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.01, top=0.99)
    if path is not None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=dpi)
    return fig
