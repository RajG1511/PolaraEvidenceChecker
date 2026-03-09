"""
One-time script to pre-compute and store subcriteria embeddings.

Run this whenever you add or change reference text in any controls/ JSON file:

    python scripts/build_references.py

It reads each JSON file, embeds the reference_text for every subcriterion,
and writes the resulting float list back into the "embedding" field.
"""

import json
from pathlib import Path

# We import from our own package — make sure you're running from the project root
# (or have the package installed with `pip install -e .`)
from polara_checker.embeddings import embedQuery

CONTROLS_DIR = Path(__file__).parent.parent / "controls"


def build_references() -> None:
    control_files = sorted(CONTROLS_DIR.glob("*.json"))

    if not control_files:
        print(f"No JSON files found in {CONTROLS_DIR}")
        return

    for filepath in control_files:
        print(f"Processing {filepath.name}...")

        with filepath.open("r", encoding="utf-8") as f:
            control = json.load(f)

        # Collect all reference texts so we can embed them in one batch call.
        # Batching is faster than calling embed() once per subcriterion because
        # the model processes a whole batch in one GPU/CPU pass.
        subcriteria = control.get("subcriteria", [])
        reference_texts = [s["reference_text"] for s in subcriteria]

        if not reference_texts:
            print(f"  ⚠ No subcriteria found, skipping.")
            continue

        # embed() accepts a list and returns shape (N, 384)
        vectors = embedQuery(reference_texts)  # numpy array: (N, 384)

        # Write each vector back into its subcriterion dict
        for subcriterion, vector in zip(subcriteria, vectors):
            # .tolist() converts numpy float32 → plain Python floats
            # so json.dump() can serialize them without errors
            subcriterion["embedding"] = vector.tolist()

        # Write the updated JSON back to disk, preserving formatting
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(control, f, indent=2)

        print(f"  ✓ Embedded {len(subcriteria)} subcriteria")

    print("\nDone. All control files updated with embeddings.")


if __name__ == "__main__":
    build_references()