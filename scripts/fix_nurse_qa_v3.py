"""Fix answer_nurse_questions to use _generate_base instead of _pipeline.

The MedGemmaWrapper uses self._generate(image, prompt) and
self._generate_base(image, prompt) — not self._pipeline.

Run on VM:
    python3 ~/WoundChrono/fix_nurse_qa_v3.py
"""

from pathlib import Path

BACKEND = Path.home() / "WoundChrono" / "backend" / "app"


def fix_method():
    p = BACKEND / "models" / "medgemma.py"
    text = p.read_text()

    # Replace the broken _pipeline-based implementation with _generate_base
    old_method = '''    def answer_nurse_questions(
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

    new_method = '''    def answer_nurse_questions(
        self,
        nurse_notes: str,
        time_scores: dict,
        image=None,
    ) -> list[str]:
        """Answer each nurse question via a focused MedGemma call.

        Uses _generate_base (LoRA disabled) for clinical reasoning.
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

        if image is None:
            logger.warning("answer_nurse_questions: no image provided, skipping.")
            return []

        try:
            raw = self._generate_base(image, prompt, max_new_tokens=400)
        except Exception as exc:
            logger.warning("answer_nurse_questions failed: %s", exc)
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

    if old_method in text:
        text = text.replace(old_method, new_method)
        p.write_text(text)
        print("Fixed answer_nurse_questions: _pipeline -> _generate_base.")
        return True
    else:
        print("ERROR: Could not find old method. Checking if already fixed...")
        if "_generate_base" in text and "answer_nurse_questions" in text:
            print("  Already uses _generate_base.")
            return True
        print("  Method not found — check manually.")
        return False


if __name__ == "__main__":
    ok = fix_method()
    if ok:
        print("\nDone. Restart backend to apply.")
    else:
        print("\nFailed.")
