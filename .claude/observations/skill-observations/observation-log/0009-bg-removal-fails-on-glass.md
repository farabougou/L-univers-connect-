---
id: 9
title: "Background removal treats transparent glass products as background"
status: open
type: open-source
skill: [studio-quality]
proposes_skill: []
target_file: [.claude/skills/studio-quality/SKILL.md]
siblings_checked: "studio: studio-quality added (pièges list); studio-motion-system excluded — no media prep (assumed); studio-polish-pass excluded (assumed)"
area: "Media prep / cut-outs"
date: 2026-10-22
session_context: "Fanta shop ad: hyperframes remove-background on TikTok covers of glass jars"
parked_until:
resolved:
resolution:
reference:
commands_verified: none
---

**Issue:** hyperframes remove-background removed the glass jars themselves on 3 of 4 covers (kept hands and tray), and left the one usable jar half transparent (alpha 120–200 inside the glass). The jar also touched the frame edge, so its corner was cut flat.

**Suggested improvement:** Add to the pitfalls: check every cut-out on a solid colour before use; repair with the largest alpha component + binary_fill_holes (opaque silhouette), then 1 px erode + blur; for glass, prefer framed photo tiles over cut-outs.

**Principle:** An automatic cut-out is a draft until it has been seen on a flat contrasting background.
