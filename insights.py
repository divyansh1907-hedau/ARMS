"""
Performance Insights Generator
--------------------------------
Produces the "Performance Insights" text block shown on the Enhanced Report
Generator and on report cards — rule-based (works with zero AI dependency),
matching the tone of the thesis's report card mockups.
"""


def generate_insights(row):
    subjects = row.get("subjects", {})
    pct = row.get("percentage", 0)
    grade = row.get("grade", "")

    weak = sorted(
        ((name, s["percentage"]) for name, s in subjects.items()),
        key=lambda x: x[1],
    )[:2]
    strong = max(subjects.items(), key=lambda kv: kv[1]["percentage"], default=None)

    lines = []

    if strong and strong[1]["percentage"] >= 80:
        lines.append(
            f"Outstanding work in {strong[0]} with a score of "
            f"{strong[1]['score']:.0f}/{strong[1]['max_marks']:.0f}! This is a key strength."
        )

    if pct < 40:
        weak_txt = ", ".join(f"{n} ({s:.0f}%)" for n, s in weak if s < 50)
        lines.append(
            f"To significantly improve your overall results, focusing on these "
            f"subjects is recommended: {weak_txt}." if weak_txt else
            "Focus on revising all subjects to build a stronger foundation."
        )
        summary = (
            f"Overall Summary: This result ({pct}%) indicates a need for immediate "
            f"and dedicated focus across all subjects. It's crucial to review the "
            f"material and seek help to build a stronger understanding."
        )
    elif pct < 75:
        weak_txt = ", ".join(f"{n} ({s:.0f}%)" for n, s in weak)
        lines.append(
            f"You're performing well across the board! To reach the next level, "
            f"you could focus on {weak_txt}."
        )
        summary = (
            f"Overall Summary: A solid performance with a {pct}% average. "
            f"Grade {grade} reflects steady understanding — a bit more focus on "
            f"weaker subjects will push this higher."
        )
    else:
        lines.append("Excellent, consistent performance across subjects.")
        summary = (
            f"Overall Summary: A very strong performance with a {pct}% average. "
            f"You have a solid grasp of the subjects. Well done!"
        )

    return {
        "highlights": lines,
        "summary": summary,
    }
