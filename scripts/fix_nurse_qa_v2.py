"""Fix nurse Q&A: dedicated inference call instead of JSON field.

The 4B model can't reliably produce nurse_answers inside the report JSON
(duplicates, hallucinations, wrong questions). Solution:
1. Revert _build_report_prompt to simple JSON schema (no nurse_answers)
2. Remove nurse_answers from _report_json_to_markdown
3. Add answer_nurse_questions() method to MedGemmaWrapper
4. Add Step 7b in wound_agent.py: dedicated Q&A call + append to report

Run on VM:
    python3 ~/WoundChrono/fix_nurse_qa_v2.py
"""

from __future__ import annotations

from pathlib import Path

BACKEND = Path.home() / "WoundChrono" / "backend" / "app"


def patch_medgemma():
    p = BACKEND / "models" / "medgemma.py"
    text = p.read_text()

    # --- 1. Remove nurse Q&A branching from _build_report_prompt ---
    # Replace the entire if/else block with just the simple schema

    old_block = """    # Detect nurse questions for Q&A
    has_nurse_questions = False
    if nurse_notes:
        has_nurse_questions = (
            '?' in nurse_notes
            or any(
                kw in nurse_notes.lower()
                for kw in ('should', 'can i', 'do i', 'is it', 'what', 'how', 'when', 'which', 'would', 'could')
            )
        )

    if has_nurse_questions:
        parts.append(
            '\\nIMPORTANT \u2014 NURSE QUESTIONS DETECTED:\\n'
            'The nurse notes contain clinical questions that require specific answers.\\n'
            'Rules for the "nurse_answers" array:\\n'
            '1. One entry per question found in the nurse notes.\\n'
            '2. Each entry must START by quoting the question, then give a direct answer.\\n'
            '   Format: "Q: [nurse question] \u2014 A: [your answer]"\\n'
            '3. Reference the actual TIME scores and wound image findings in each answer.\\n'
            '4. Be specific: name dressing types (foam, alginate, hydrocolloid), medications, '
            'or thresholds rather than saying "consider changing" or "consult physician".\\n'
            '5. Keep each answer to 1-2 sentences maximum.\\n'
            '6. Do NOT duplicate content from the "interventions" field.\\n'
        )
        parts.append(
            '\\nRespond in English only. Respond with this exact JSON structure:\\n'
            '{"summary": "2-3 sentence clinical summary of wound status",'
            ' "wound_status": "current wound status description",'
            ' "change_analysis": "change since last visit or baseline note",'
            ' "interventions": ["intervention 1", "intervention 2", ...],'
            ' "nurse_answers": ["answer to question 1", "answer to question 2", ...],'
            ' "follow_up": "follow-up timeline recommendation"}'
        )
    else:
        parts.append(
            '\\nRespond in English only. Respond with this exact JSON structure:\\n'
            '{"summary": "2-3 sentence clinical summary of wound status",'
            ' "wound_status": "current wound status description",'
            ' "change_analysis": "change since last visit or baseline note",'
            ' "interventions": ["intervention 1", "intervention 2", ...],'
            ' "follow_up": "follow-up timeline recommendation"}'
        )
    return "\\n".join(parts)"""

    new_block = """    parts.append(
        '\\nRespond in English only. Respond with this exact JSON structure:\\n'
        '{"summary": "2-3 sentence clinical summary of wound status",'
        ' "wound_status": "current wound status description",'
        ' "change_analysis": "change since last visit or baseline note",'
        ' "interventions": ["intervention 1", "intervention 2", ...],'
        ' "follow_up": "follow-up timeline recommendation"}'
    )
    return "\\n".join(parts)"""

    if old_block in text:
        text = text.replace(old_block, new_block)
        print("  [1] Removed nurse Q&A branching from _build_report_prompt.")
    else:
        print("  [1] WARNING: Could not find nurse Q&A block. Check manually.")
        return False

    # --- 2. Remove nurse_answers handling from _report_json_to_markdown ---
    old_markdown = """    # Nurse Q&A section (if model answered nurse questions)
    nurse_answers = report_data.get("nurse_answers", [])
    if isinstance(nurse_answers, list) and nurse_answers:
        lines.extend(["", "### Clinical Guidance"])
        lines.append("*Answers to nurse questions based on wound assessment:*")
        lines.append("")
        for ans in nurse_answers:
            lines.append(f"- {ans}")

    lines.extend(["""

    new_markdown = """    lines.extend(["""

    if old_markdown in text:
        text = text.replace(old_markdown, new_markdown)
        print("  [2] Removed nurse_answers from _report_json_to_markdown.")
    else:
        print("  [2] WARNING: nurse_answers markdown block not found.")

    # --- 3. Add answer_nurse_questions() method to MedGemmaWrapper ---
    if "answer_nurse_questions" in text:
        print("  [3] answer_nurse_questions() already exists, skipping.")
    else:
        # Insert at end of class (before any module-level code after the class)
        # The class ends with detect_contradiction's return. Add after that.
        insert_marker = '            "detail": result.get("detail"),\n        }'
        method_code = '''

    # ------------------------------------------------------------------
    # Nurse Q&A — dedicated inference (separate from report JSON)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_questions(nurse_notes: str) -> list[str]:
        """Extract question sentences from nurse notes."""
        import re as _re
        sentences = _re.split(r'(?<=[.?!])\\s+', nurse_notes)
        return [s.strip() for s in sentences if '?' in s and len(s.strip()) > 10]

    def answer_nurse_questions(
        self,
        nurse_notes: str,
        time_scores: dict,
        image=None,
    ) -> list[str]:
        """Answer each nurse question via a focused MedGemma call.

        Returns list of "Q: ... — A: ..." strings, or empty list.
        """
        questions = self._extract_questions(nurse_notes)
        if not questions:
            return []

        parts = [
            "You are a wound care clinical decision support assistant.",
            "Based on the wound image and TIME assessment below, answer each nurse question.",
            "",
            "TIME Assessment:",
        ]
        for dim in ("tissue", "inflammation", "moisture", "edge"):
            info = time_scores.get(dim, {})
            parts.append(f"  {dim.capitalize()}: {info.get('score', 'N/A')}/1.0 ({info.get('type', 'N/A')})")

        parts.append("")
        parts.append("Nurse questions:")
        for idx, q in enumerate(questions, 1):
            parts.append(f"  {idx}. {q}")

        parts.extend([
            "",
            "Answer each question on a separate numbered line.",
            "Be SPECIFIC: name dressing types (foam, alginate, hydrocolloid, silver-impregnated),",
            "medications (mupirocin, metronidazole), or measurable thresholds.",
            "Reference the TIME scores when relevant.",
            "Keep each answer to 1-2 sentences. English only.",
        ])

        prompt = "\\n".join(parts)
        content = []
        if image is not None:
            content.append({"type": "image", "image": image})
        content.append({"type": "text", "text": prompt})

        try:
            # Use base model (disable LoRA) for reasoning
            if hasattr(self._model, "disable_adapter_layers"):
                self._model.disable_adapter_layers()

            output = self._pipeline(
                text=[{"role": "user", "content": content}],
                max_new_tokens=400,
            )
            raw = output[0]["generated_text"][-1]["content"]

            if hasattr(self._model, "enable_adapter_layers"):
                self._model.enable_adapter_layers()
        except Exception as exc:
            logger.warning("answer_nurse_questions failed: %s", exc)
            if hasattr(self._model, "enable_adapter_layers"):
                self._model.enable_adapter_layers()
            return []

        # Parse numbered answers
        import re as _re
        raw_lines = [l.strip() for l in raw.strip().split("\\n") if l.strip()]
        answers = []

        for idx, q in enumerate(questions):
            matched = None
            for line in raw_lines:
                for pfx in [f"{idx+1}.", f"{idx+1})", f"{idx+1}:"]:
                    if line.startswith(pfx):
                        matched = line[len(pfx):].strip()
                        break
                if matched:
                    break
            if not matched and idx < len(raw_lines):
                matched = raw_lines[idx]
            if not matched:
                matched = "Clinical evaluation recommended."

            # Sanitize non-ASCII hallucinations
            matched = _re.sub(r"[^\\x00-\\x7F]+", "", matched).strip()
            if len(matched) < 5:
                matched = "Clinical evaluation recommended."
            # Remove leading "A:" if present
            if matched.lower().startswith("a:"):
                matched = matched[2:].strip()

            answers.append(f"Q: {q} \\u2014 A: {matched}")

        return answers'''

        if insert_marker in text:
            text = text.replace(insert_marker, insert_marker + method_code)
            print("  [3] Added answer_nurse_questions() method.")
        else:
            print("  [3] WARNING: Could not find insertion point for method.")
            return False

    p.write_text(text)
    print("medgemma.py: patched.")
    return True


def patch_wound_agent():
    """Add Step 7b (nurse Q&A) to wound_agent.py after report generation."""
    p = BACKEND / "agents" / "wound_agent.py"
    text = p.read_text()

    if "answer_nurse_questions" in text:
        print("wound_agent.py: nurse Q&A already present, skipping.")
        return True

    # Insert after Step 7 report generation and before Step 8
    old_step8 = '        # Step 8: Alert determination'

    new_step7b_and_8 = '''        # Step 7b: Nurse Q&A (dedicated inference if questions detected)
        if nurse_notes and ('?' in nurse_notes or any(
            kw in nurse_notes.lower()
            for kw in ('should', 'can i', 'do i', 'is it', 'what', 'how', 'when', 'which')
        )):
            logger.info("Step 7b: Answering nurse questions (dedicated call).")
            try:
                nurse_answers = self.medgemma.answer_nurse_questions(
                    nurse_notes, time_scores, image=image,
                )
                if nurse_answers:
                    logger.info("Step 7b: Got %d nurse answers.", len(nurse_answers))
                    guidance = ['', '### Clinical Guidance']
                    guidance.append('*Answers to nurse questions based on wound assessment:*')
                    guidance.append('')
                    for ans in nurse_answers:
                        guidance.append(f'- {ans}')
                    report += '\\n' + '\\n'.join(guidance)
            except Exception as exc:
                logger.warning("Step 7b: Nurse Q&A failed: %s", exc)
        else:
            logger.info("Step 7b: No nurse questions detected, skipping.")

        # Step 8: Alert determination'''

    if old_step8 in text:
        text = text.replace(old_step8, new_step7b_and_8)
        p.write_text(text)
        print("wound_agent.py: patched with Step 7b nurse Q&A.")
        return True
    else:
        print("wound_agent.py: WARNING: Could not find Step 8 marker.")
        return False


if __name__ == "__main__":
    ok1 = patch_medgemma()
    ok2 = patch_wound_agent()
    if ok1 and ok2:
        print("\nDone. Restart backend to apply.")
    else:
        print("\nPartial failure — check output above.")
