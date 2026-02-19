"""Refine nurse Q&A prompt for better answer quality.

The initial prompt produces vague, duplicate answers. This patch makes the
prompt more directive: each question must be quoted, answered with specific
clinical details referencing TIME scores, and kept to 1-2 sentences.

Run on VM:
    python3 ~/WoundChrono/refine_nurse_qa_prompt.py
"""

from pathlib import Path

BACKEND = Path.home() / "WoundChrono" / "backend" / "app"


def refine_prompt():
    p = BACKEND / "models" / "medgemma.py"
    text = p.read_text()

    # Old vague instruction block
    old_instruction = (
        "            '\\nIMPORTANT: The nurse notes contain clinical questions. '\n"
        "            'Answer each question specifically in the \"nurse_answers\" field, '\n"
        "            'using the wound image, TIME scores, and clinical context. '\n"
        "            'Each answer should be evidence-based and actionable.'\n"
    )

    # New directive instruction block
    new_instruction = (
        "            '\\nIMPORTANT — NURSE QUESTIONS DETECTED:\\n'\n"
        "            'The nurse notes contain clinical questions that require specific answers.\\n'\n"
        "            'Rules for the \"nurse_answers\" array:\\n'\n"
        "            '1. One entry per question found in the nurse notes.\\n'\n"
        "            '2. Each entry must START by quoting the question, then give a direct answer.\\n'\n"
        "            '   Format: \"Q: [nurse question] — A: [your answer]\"\\n'\n"
        "            '3. Reference the actual TIME scores and wound image findings in each answer.\\n'\n"
        "            '4. Be specific: name dressing types (foam, alginate, hydrocolloid), medications, '\n"
        "            'or thresholds rather than saying \"consider changing\" or \"consult physician\".\\n'\n"
        "            '5. Keep each answer to 1-2 sentences maximum.\\n'\n"
        "            '6. Do NOT duplicate content from the \"interventions\" field.\\n'\n"
    )

    if old_instruction not in text:
        print("ERROR: Could not find old instruction block in medgemma.py")
        print("Looking for alternative patterns...")

        # Try a more flexible search
        if "nurse notes contain clinical questions" in text:
            # Find the line and show context
            lines = text.split("\n")
            for i, line in enumerate(lines):
                if "nurse notes contain clinical questions" in line:
                    print(f"  Found at line {i+1}: {line.strip()}")
            print("\nManual intervention needed — old_instruction doesn't match exactly.")
        else:
            print("Nurse Q&A instruction not found at all. Was apply_nurse_qa.py run?")
        return False

    text = text.replace(old_instruction, new_instruction)
    p.write_text(text)
    print("medgemma.py: nurse Q&A prompt refined.")
    return True


if __name__ == "__main__":
    ok = refine_prompt()
    if ok:
        print("\nDone. Restart backend to apply.")
    else:
        print("\nFailed. Check output above.")
