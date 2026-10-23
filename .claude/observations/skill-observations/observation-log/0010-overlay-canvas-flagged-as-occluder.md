---
id: 10
title: "Layout check flags blended overlay canvases as opaque occluders; duplicate wrapper ids double CSS offsets"
status: open
type: open-source
skill: [studio-quality]
proposes_skill: []
target_file: [.claude/skills/studio-quality/SKILL.md]
siblings_checked: "studio: studio-quality added (pièges list); studio-motion-system excluded — helpers unaffected (assumed); studio-polish-pass excluded (assumed)"
area: "QA / hyperframes check"
date: 2026-10-22
session_context: "Fanta shop ad: smoke and spray canvases with mix-blend-mode screen over headlines"
parked_until:
resolved:
resolution:
reference:
commands_verified: "npx hyperframes@0.8.177 check (layout-audit.browser.js isOpaqueOccluder: opacity chain < 0.6 is never an occluder; data-layout-allow-occlusion is read on the TEXT element only)"
---

**Issue:** A full-frame canvas with mix-blend-mode: screen counts as an opaque raster occluder, so every headline under the smoke failed text_occluded. Putting data-layout-allow-occlusion on the canvas does nothing. Separately, a wrapper div and its SVG shared one id, so the #id CSS offset applied twice and the tray rendered off-screen.

**Suggested improvement:** Pitfalls: give overlay canvases opacity 0.5 on the element and double the drawn alpha; never reuse an id on a wrapper and its child.

**Principle:** Read the checker's own rule before working around a false positive.
