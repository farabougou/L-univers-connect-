---
id: 6
title: "visibility:visible on a child escaped its scene's hidden state"
status: open
type: open-source
skill: [studio-quality]
proposes_skill: []
target_file: []
siblings_checked: "studio: studio-quality added (Pièges list); studio-motion-system excluded — no scene switching API (assumed); studio-polish-pass excluded (assumed)"
area: "Pièges déjà rencontrés / scene switching"
date: 2026-10-21
session_context: "Enoryx installations ad, phone screen states inside a scene"
parked_until:
resolved:
resolution:
reference:
commands_verified: none
---

**Issue:** Two screen states inside the phone scene were switched with visibility. Once the second was set visible, it stayed on screen after the scene was hidden, because a child's visibility:visible overrides a hidden ancestor. The HyperFrames check flagged it (visibility_escapes_segment).

**Suggested improvement:** Pitfall line: switch states inside a scene with opacity, keep visibility for the scene container only.

**Principle:** Visibility is inherited but overridable, so only the outermost container of a time segment may use it; inner states use opacity.
