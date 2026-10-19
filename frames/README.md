# Netrr evaluation frames

This directory is the fixed input set for the claim-level benchmark (plan v2,
section 5). Target 800 to 1,200 frames from VizWiz, ORBIT, and Netrr hardware
capture.

Status (19 Oct 2026): seeded from the prototype's `test_images/` only. Three
images, one with a label:

- `road.png` — auto-annotated YOLO segmentation label in
  `road_auto_annotate_labels/road.txt`.
- `bars.png` — unlabelled, pending annotation.
- `path.png` — unlabelled, pending annotation.

Annotation is two-stage: ground-truth claims, then harm grading with 3 to 5
members of the Ahmedabad Blind People Association. No frames are harm-graded
yet. Do not report benchmark numbers until annotation is complete.

The manifest of record is `manifest.jsonl`.
