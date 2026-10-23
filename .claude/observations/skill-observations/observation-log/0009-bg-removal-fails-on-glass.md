---
id: 9
title: "Background removal fails on glass, white and pale products (and on dark products on a same-colour backdrop)"
status: open
type: open-source
skill: [studio-quality]
proposes_skill: []
target_file: [.claude/skills/studio-quality/SKILL.md]
siblings_checked: "studio: studio-quality added (pièges list); studio-motion-system excluded — no media prep (assumed); studio-polish-pass excluded (assumed)"
area: "Media prep / cut-outs"
date: 2026-10-22
session_context: "Fanta shop ad (TikTok covers of glass jars); Farmasi ad (white-background catalogue packshots, dark-green makeup on a green banner)"
parked_until:
resolved:
resolution:
reference:
commands_verified: none
---

**Issue:** hyperframes remove-background removed the glass jars themselves on 3 of 4 covers (kept hands and tray), and left the one usable jar half transparent (alpha 120–200 inside the glass). The jar also touched the frame edge, so its corner was cut flat.

**Second instance (Farmasi ad, 2026-10-23):** on 9 catalogue packshots, the model returned an empty mask for a white glass serum, kept only a corner of a pale lilac box, and returned nothing for dark-green makeup on a dark-green banner. What worked for white backgrounds: background = near-white pixels connected to the image border (flood fill, scipy.ndimage.label), product = the rest with holes filled; a white transparent bottle needed the convex hull of its non-white pixels. Cut-outs from white backgrounds also kept a 1–2 px white halo (visible on coloured scenes) and a baked floor shadow under one box: a 2 px erode and a manual bottom trim fixed them. The dark-on-dark makeup was used as a full photo plate instead.

**Suggested improvement:** Add to the pitfalls: check every cut-out on a solid colour before use; repair with the largest alpha component + binary_fill_holes (opaque silhouette), then 1 px erode + blur; for glass, prefer framed photo tiles over cut-outs; for packshots on pure white, use the border flood fill (convex hull for transparent bottles) before the model, then a 2 px erode against the white halo.

**Principle:** An automatic cut-out is a draft until it has been seen on a flat contrasting background.
