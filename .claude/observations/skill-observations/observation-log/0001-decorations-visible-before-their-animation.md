---
id: 1
title: "Static decorations (round caps, highlight boxes) show before their animated content"
status: open
type: open-source
skill: [studio-quality, studio-motion-system]
proposes_skill: []
target_file: []
siblings_checked: "studio: studio-quality added (Pièges list); studio-motion-system added (text helpers used for highlight boxes); studio-polish-pass excluded — applies studio-quality's list (assumed)"
area: "Pièges déjà rencontrés / text and logo reveals"
date: 2026-10-21
session_context: "Mams avatar presentation video (videos/mams-avatar), snapshot review before render"
parked_until:
resolved:
resolution:
reference: "videos/mams-avatar/.src/gen.py"
commands_verified: none
---

**Issue:** Three defects of one shape, found on snapshots. (1) An SVG logo drawn with stroke-dasharray 100 / dashoffset 100 and round linecaps showed orange dots before its draw started: a zero-length dash with round caps still paints the caps. (2) A keyword highlight box (orange background) was visible, empty, before its word arrived. (3) One box shared by two keywords stayed half empty between the two words.

**Suggested improvement:** Add to studio-quality "Pièges déjà rencontrés": hide a dasharray draw-on SVG until its draw starts (visibility set at the draw time); fade/scale a keyword box with its word, never with its line; one box per keyword word. Mention the box pattern next to the text helpers in studio-motion-system.

**Principle:** An element's decoration (caps, backgrounds, borders, shadows) is visible even when its animated content is at zero, so every decoration must be gated by the same timing as the content it frames.
