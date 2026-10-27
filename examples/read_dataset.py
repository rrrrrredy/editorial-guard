"""Read published editorial samples by source family; no model calls or labels inferred."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import statistics


def read_rows(path):
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.split("\n") if line.strip()]
    return json.loads(text)


def summarize(rows, dataset_dir):
    result = {}
    for suite in sorted({r["suite"] for r in rows}):
        selected = [r for r in rows if r["suite"] == suite]
        natural = [r for r in selected if r["provenance"]["route"] == "natural"]
        families = defaultdict(list)
        for row in selected:
            families[row["source_group_id"]].append(row)
        manifest_path = dataset_dir / suite / "family-manifest.json"
        if not manifest_path.exists():
            manifest_path = dataset_dir / "family-manifest.json"
        manifest = {r["source_group_id"]: r for r in read_rows(manifest_path)} if manifest_path.exists() else {}
        generators = Counter()
        for row in natural:
            generator = row["provenance"].get("generator", manifest.get(row["source_group_id"], {}).get("generator", "unknown"))
            requested = re.search(r"正文约([^。]+)", row["instruction"])
            generators[(generator, requested.group(1) if requested else "unknown")] += 1
        lengths = [len(r["input_text"]) for r in natural]
        templates = defaultdict(list)
        for row in natural:
            if "source_bundle" in row:
                facts = " | ".join(row["source_bundle"]["facts"][:3])
                facts = re.sub(r"虚构[^，。\n]*?项目\d+号", "[project]", facts)
                templates[re.sub(r"\d+", "#", facts)].append(row["genre"])
        result[suite] = {
            "instances": len(selected), "source_families": len(families),
            "natural_model_outputs": len(natural),
            "distinct_texts": len({r["input_text"] for r in selected}),
            "identical_text_pairs": sum(len(v) == 2 and v[0]["input_text"] == v[1]["input_text"] for v in families.values()),
            "disagreement_status": dict(Counter(r["disagreement_status"] for r in selected)),
            "natural_genres": dict(Counter(r["genre"] for r in natural)),
            "natural_stages": dict(Counter(r["stage"] for r in natural)),
            "generator_by_requested_length": [{"generator": g, "requested_length": l, "families": n} for (g, l), n in sorted(generators.items())],
            "first_three_fact_templates": [{"normalized_facts": key, "families": len(genres), "genres": dict(Counter(genres))} for key, genres in sorted(templates.items())] if templates else None,
            "natural_unicode_characters": {"min": min(lengths), "median": statistics.median(lengths), "max": max(lengths), "at_least_1000": sum(n >= 1000 for n in lengths)} if lengths else None,
            "counting_note": "Lengths include Markdown, whitespace and punctuation. Pairs, views and annotations do not add independent families. Natural means model output, not human writing.",
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).resolve().parents[1] / "datasets/public_samples.json")
    parser.add_argument("--suite", choices=["StyleBench-ZH", "DeliveryBench-ZH"])
    parser.add_argument("--family", help="Return both original and controlled records, including available source/annotation fields.")
    args = parser.parse_args()
    rows = read_rows(args.input)
    if args.suite:
        rows = [r for r in rows if r["suite"] == args.suite]
    if args.family:
        rows = [r for r in rows if r["source_group_id"] == args.family]
        if not rows:
            parser.error("No published sample matches this family and suite.")
        output = {"view": "analyst_only_not_solver_input", "annotation_note": "Model judgments and disagreements are retained; this is not human gold labeling.", "samples": rows}
    else:
        output = summarize(rows, args.input.parent)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
