"""Add nurse Q&A feature to report generation.

When nurse notes contain questions, MedGemma answers them in a dedicated
'Clinical Guidance' section, separate from the general recommendations.

Run on the VM:
    python3 ~/WoundChrono/apply_nurse_qa.py
"""

from __future__ import annotations

import re
from pathlib import Path

BACKEND = Path.home() / "WoundChrono" / "backend" / "app"


def _has_questions(text: str) -> bool:
    """Check if text contains questions."""
    if "?" in text:
        return True
    question_starters = (
        "should", "can i", "can we", "do i", "do we",
        "is it", "is there", "are there", "what", "how",
        "when", "which", "would", "could",
    )
    lower = text.lower().strip()
    for starter in question_starters:
        if lower.startswith(starter) or f". {starter}" in lower or f", {starter}" in lower:
            return True
    return False


def patch_medgemma():
    """Patch _build_report_prompt and _report_json_to_markdown for nurse Q&A."""
    p = BACKEND / "models" / "medgemma.py"
    text = p.read_text()

    if "nurse_answers" in text:
        print("medgemma.py: nurse Q&A already patched, skipping.")
        return

    # 1. Patch _build_report_prompt: add nurse_answers to JSON schema when questions detected
    old_prompt_end = (
        "    if contradiction.get(\"contradiction\"):\n"
        "        parts.append(f\"\\n## Contradiction detected\\n{contradiction.get('detail', 'N/A')}\")\n"
        "    parts.append(\n"
        "        '\\nRespond in English only. Respond with this exact JSON structure:\\n'\n"
        "        '{\"summary\": \"2-3 sentence clinical summary of wound status\",'\n"
        "        ' \"wound_status\": \"current wound status description\",'\n"
        "        ' \"change_analysis\": \"change since last visit or baseline note\",'\n"
        "        ' \"interventions\": [\"intervention 1\", \"intervention 2\", ...],'\n"
        "        ' \"follow_up\": \"follow-up timeline recommendation\"}'\n"
        "    )\n"
        "    return \"\\n\".join(parts)"
    )

    new_prompt_end = (
        "    if contradiction.get(\"contradiction\"):\n"
        "        parts.append(f\"\\n## Contradiction detected\\n{contradiction.get('detail', 'N/A')}\")\n"
        "\n"
        "    # Detect nurse questions for Q&A\n"
        "    has_nurse_questions = False\n"
        "    if nurse_notes:\n"
        "        has_nurse_questions = (\n"
        "            '?' in nurse_notes\n"
        "            or any(\n"
        "                kw in nurse_notes.lower()\n"
        "                for kw in ('should', 'can i', 'do i', 'is it', 'what', 'how', 'when', 'which', 'would', 'could')\n"
        "            )\n"
        "        )\n"
        "\n"
        "    if has_nurse_questions:\n"
        "        parts.append(\n"
        "            '\\nIMPORTANT: The nurse notes contain clinical questions. '\n"
        "            'Answer each question specifically in the \"nurse_answers\" field, '\n"
        "            'using the wound image, TIME scores, and clinical context. '\n"
        "            'Each answer should be evidence-based and actionable.'\n"
        "        )\n"
        "        parts.append(\n"
        "            '\\nRespond in English only. Respond with this exact JSON structure:\\n'\n"
        "            '{\"summary\": \"2-3 sentence clinical summary of wound status\",'\n"
        "            ' \"wound_status\": \"current wound status description\",'\n"
        "            ' \"change_analysis\": \"change since last visit or baseline note\",'\n"
        "            ' \"interventions\": [\"intervention 1\", \"intervention 2\", ...],'\n"
        "            ' \"nurse_answers\": [\"answer to question 1\", \"answer to question 2\", ...],'\n"
        "            ' \"follow_up\": \"follow-up timeline recommendation\"}'\n"
        "        )\n"
        "    else:\n"
        "        parts.append(\n"
        "            '\\nRespond in English only. Respond with this exact JSON structure:\\n'\n"
        "            '{\"summary\": \"2-3 sentence clinical summary of wound status\",'\n"
        "            ' \"wound_status\": \"current wound status description\",'\n"
        "            ' \"change_analysis\": \"change since last visit or baseline note\",'\n"
        "            ' \"interventions\": [\"intervention 1\", \"intervention 2\", ...],'\n"
        "            ' \"follow_up\": \"follow-up timeline recommendation\"}'\n"
        "        )\n"
        "    return \"\\n\".join(parts)"
    )

    text = text.replace(old_prompt_end, new_prompt_end)

    # 2. Patch _report_json_to_markdown: add Clinical Guidance section
    old_followup = (
        "    lines.extend([\n"
        "        \"\",\n"
        "        \"### Follow-up\",\n"
        "        report_data.get(\"follow_up\", \"Schedule follow-up as clinically indicated.\"),\n"
        "        \"\",\n"
        "    ])\n"
        "    return \"\\n\".join(lines)"
    )

    new_followup = (
        "    # Nurse Q&A section (if model answered nurse questions)\n"
        "    nurse_answers = report_data.get(\"nurse_answers\", [])\n"
        "    if isinstance(nurse_answers, list) and nurse_answers:\n"
        "        lines.extend([\"\", \"### Clinical Guidance\"])\n"
        "        lines.append(\"*Answers to nurse questions based on wound assessment:*\")\n"
        "        lines.append(\"\")\n"
        "        for ans in nurse_answers:\n"
        "            lines.append(f\"- {ans}\")\n"
        "\n"
        "    lines.extend([\n"
        "        \"\",\n"
        "        \"### Follow-up\",\n"
        "        report_data.get(\"follow_up\", \"Schedule follow-up as clinically indicated.\"),\n"
        "        \"\",\n"
        "    ])\n"
        "    return \"\\n\".join(lines)"
    )

    text = text.replace(old_followup, new_followup)

    p.write_text(text)
    print("medgemma.py: patched with nurse Q&A support.")


if __name__ == "__main__":
    patch_medgemma()
    print("\nDone. Restart backend to apply.")
