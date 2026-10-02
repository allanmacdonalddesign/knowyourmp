"""Brief submission guide: pulls the committee's actual deadline, limits, conditions and form. Never submits anything."""
from datetime import date

from ..sources.committees import CommitteeMember, Study, Submission


def render(study: Study, sub: Submission, members: list[CommitteeMember], today: date, my_mp_name: str | None = None) -> str:
    lines = [f"HOW TO SUBMIT A BRIEF: {study.code}: {study.title}", ""]
    if study.deadline:
        days = (study.deadline - today).days
        when = f"{study.deadline:%A, %B %d, %Y} ({days} days left)" if days >= 0 else f"{study.deadline} (PASSED)"
        lines.append(f"Deadline: {when}, 11:59 p.m. Eastern")
    else:
        lines.append("Deadline: none shown on the study page; check with the committee clerk before relying on that.")
    if study.brief_limit:
        lines.append(f"Length: {study.brief_limit}")
    if study.briefs is not None:
        lines.append(f"So far: {study.briefs} briefs" + (f", {study.witnesses} witnesses" if study.witnesses is not None else ""))
    lines += ["", "Official conditions (from the submission page):"]
    lines += [f"  - {c}" for c in sub.conditions] or ["  - (could not read the conditions; open the form link below)"]
    lines += ["", "What to do:"]
    steps = [
        "Write your brief in your own words, within the length limit. A suggested outline: who you are and why you care (2 to 3 sentences); "
        "your specific recommendations, numbered; the evidence or experience behind each; the one change you most want the committee to make.",
        "Keep it respectful and on the study topic; briefs with crude language or irrelevant content are rejected.",
        f"Submit it yourself through the official form: {sub.form_url or study.url}",
    ]
    if sub.guide_url:
        steps.append(f"Read the House's guide for briefs first: {sub.guide_url}")
    steps.append("Optional but useful: email the committee members (not only your own MP) a two-line note pointing to your brief.")
    lines += [f"  {i}. {t}" for i, t in enumerate(steps, 1)]
    if sub.clerk_url:
        lines.append(f"\nQuestions: contact the committee clerk: {sub.clerk_url}")
    if members:
        lines += ["", f"Committee members ({study.code}):"]
        for m in members:
            mark = "  <-- your MP" if my_mp_name and m.name == my_mp_name else ""
            lines.append(f"  - {m.name} ({m.role}, {m.party}, {m.riding}){mark}")
        lines.append(f"  Contact details: {study.url.split('/StudyActivity')[0].replace('/committees/', '/Committees/')}/Members")
    lines.append("\nThis tool does not submit anything for you.")
    return "\n".join(lines)
