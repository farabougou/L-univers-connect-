---
id: 2
title: "maskUp start offset ignored the mask padding, so letter tops leaked while waiting"
status: actioned
type: open-source
skill: [studio-motion-system]
proposes_skill: []
target_file: [videos/_studio/studio.js]
siblings_checked: "studio: studio-motion-system added (documents maskUp); studio-quality excluded — no offset value in its text (checked by grep for 118); studio-polish-pass excluded (assumed)"
area: "Text helpers / maskUp"
date: 2026-10-21
session_context: "Motion reel, scroll-stop section: words waiting under .st-mask for 0.9 s"
parked_until:
resolved: 2026-10-21
resolution: "studio.js maskUp now starts at yPercent 140 (was 118); motion-reel's vendored copy updated; older projects keep their own copy"
reference:
commands_verified: none
---

**Issue:** .st-mask has 0.14 em top and 0.2 em bottom padding, so its box is 1.34 em tall; maskUp moved words down 118 % of their own height, leaving the top 2 px of the letters visible as a dash while the words waited.

**Suggested improvement:** Done in the library. If studio-motion-system ever quotes the offset, it should say 140 % and why.

**Principle:** A hidden-start offset must be derived from the clipping container's full box, padding included, not from the moving element's own size.
