"""Revert INT4 quantization code from medgemma.py (keep nurse Q&A).

The INT4 code causes a peft/accelerate crash:
  TypeError: unhashable type: 'set' in get_balanced_memory

Run on VM:
    python3 ~/WoundChrono/revert_int4.py
"""

from pathlib import Path

BACKEND = Path.home() / "WoundChrono" / "backend" / "app"


def revert_medgemma():
    p = BACKEND / "models" / "medgemma.py"
    text = p.read_text()

    # 1. Remove quantize_4bit from __init__
    text = text.replace(
        "    def __init__(\n"
        "        self, model_name: str, device: str, *, mock: bool = False, lora_path: str = \"\",\n"
        "        quantize_4bit: bool = False,\n"
        "    ) -> None:\n"
        "        self.model_name = model_name\n"
        "        self.device = device\n"
        "        self.mock = mock\n"
        "        self.lora_path = lora_path\n"
        "        self.quantize_4bit = quantize_4bit",
        "    def __init__(\n"
        "        self, model_name: str, device: str, *, mock: bool = False, lora_path: str = \"\",\n"
        "    ) -> None:\n"
        "        self.model_name = model_name\n"
        "        self.device = device\n"
        "        self.mock = mock\n"
        "        self.lora_path = lora_path",
    )

    # 2. Revert from_pretrained to original (no quantization_config)
    text = text.replace(
        "        # INT4 quantization (NF4) if enabled\n"
        "        quant_config = None\n"
        "        if self.quantize_4bit and self.device == \"cuda\":\n"
        "            from transformers import BitsAndBytesConfig\n"
        "            quant_config = BitsAndBytesConfig(\n"
        "                load_in_4bit=True,\n"
        "                bnb_4bit_compute_dtype=torch.bfloat16,\n"
        "                bnb_4bit_quant_type=\"nf4\",\n"
        "                bnb_4bit_use_double_quant=True,\n"
        "            )\n"
        "            logger.info(\"INT4 (NF4) quantization enabled.\")\n"
        "\n"
        "        self._model = AutoModelForImageTextToText.from_pretrained(\n"
        "            self.model_name,\n"
        "            torch_dtype=torch.bfloat16,\n"
        "            device_map=\"auto\" if self.device == \"cuda\" else None,\n"
        "            trust_remote_code=True,\n"
        "            quantization_config=quant_config,\n"
        "        )",
        "        self._model = AutoModelForImageTextToText.from_pretrained(\n"
        "            self.model_name,\n"
        "            torch_dtype=torch.bfloat16,\n"
        "            device_map=\"auto\" if self.device == \"cuda\" else None,\n"
        "            trust_remote_code=True,\n"
        "        )",
    )

    p.write_text(text)
    print("medgemma.py: INT4 code reverted.")


def revert_main():
    p = BACKEND / "main.py"
    text = p.read_text()

    text = text.replace(
        "    _medgemma = MedGemmaWrapper(\n"
        "        settings.MEDGEMMA_MODEL, device, mock=mock, lora_path=settings.MEDGEMMA_LORA_PATH,\n"
        "        quantize_4bit=settings.QUANTIZE_4BIT,\n"
        "    )",
        "    _medgemma = MedGemmaWrapper(\n"
        "        settings.MEDGEMMA_MODEL, device, mock=mock, lora_path=settings.MEDGEMMA_LORA_PATH,\n"
        "    )",
    )

    p.write_text(text)
    print("main.py: quantize_4bit param removed.")


if __name__ == "__main__":
    revert_medgemma()
    revert_main()
    print("\nDone. INT4 reverted, nurse Q&A preserved.")
