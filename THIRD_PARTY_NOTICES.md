# Third-party notices

No third-party benchmark texts or private user documents enter the main synthetic dataset. Research citations do not relicense source content.

Runtime dependency jsonschema uses MIT; its installed dependencies retain their own licenses. Development tooling is not bundled into the software archive.

Reference baselines Humanizer (blader), Humanizer-zh (op7418), and Stop Slop (Hardik Pandya) use MIT. Their notices must accompany any packaged copies. Research sources and fixed commits are recorded in research/sources.jsonl. Required author and product attribution is retained.

The MIT text is sourced from the SPDX license list and CC BY 4.0 from Creative Commons.

Pinned baseline rules are redistributed unchanged under their original MIT notices in evals/third_party/Humanizer, HumanizerZH and StopSlop. Each directory includes its upstream LICENSE; manifest.json records the exact commit and the separate JSON output wrapper. These are excluded from the installable Python tool and project Skill packages.
