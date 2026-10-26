## Accessibility Audit: Dumpit v1 Mockup — re-test after fixes
**Standard:** WCAG 2.1 AA | **Date:** 26 October 2026

**Method.** Unlike the first audit (markup and colour review only), this round each of the
five artboards was rendered in headless Chromium and tested:

- **axe-core 4.10.2** with the `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa` and `best-practice`
  rule sets (includes colour contrast);
- **keyboard**: Tab through every stop, checking each has a visible focus indicator, and
  Space on a checkbox to confirm it toggles;
- **accessibility tree** (Playwright ARIA snapshot): what a screen reader is given as role,
  name and state;
- **reflow**: the frame made fluid and checked for horizontal overflow at 320 CSS px
  (the WCAG 1.4.10 width) and at 195 px (390 px at 200% zoom).

**Limits.** The canvas's own runtime isn't available outside claude.ai, so each artboard was
flattened to plain HTML with the default accent. That matches the markup exactly but not the
runtime's rendering. No real screen reader (VoiceOver, TalkBack) was used, and nothing here
tests announcements firing over time. Automated tools catch roughly a third of issues; the
manual checks above cover more, not all.

### Summary
**Issues found:** 4 | **Critical:** 0 | **Major:** 1 | **Minor:** 3

All 16 issues from the first audit are resolved. One new problem was introduced by the fix
for the capture log, and three minor ones remain.

| Screen | axe passes | axe violations | Tab stops | Without visible focus | Reflow at 320 px |
|---|---|---|---|---|---|
| Dashboard | 32 | 0 | 7 | 0 | ✅ |
| Capture & undo | 33 | **2** | 6 | 0 | ✅ |
| Pasted notes | 27 | 0 | 8 | 0 | ✅ |
| Trip | 31 | 0 | 7 | 0 | ✅ |
| Error & edge states | 27 | 0 | 5 | 0 | ✅ |

### First-audit issues: status

| # | Issue | Status | Evidence |
|---|---|---|---|
| O1 | Capture input hid its focus | ✅ Fixed | Every tab stop on all five screens shows a focus indicator |
| O2 | Checkboxes not operable | ✅ Fixed | Exposed as `checkbox` with title + due date as name; Space toggles |
| P1 | Checkbox outline 2.59:1 | ✅ Fixed | `#858E95`, 3.33:1; axe contrast rules pass |
| O3 | Ambiguous "Undo" | ✅ Fixed | "Undo expense €42 groceries", "Undo moving the dentist to Friday", … |
| R1 | Dictate was a link | ✅ Fixed | `button "Dictate"` |
| R2 | No status messages | ✅ Fixed in markup | Capture history is a `log` region; the filing error is an `alert`. Announcement timing still needs a device test |
| R3 | Trip card name too long | ✅ Fixed | Short link name |
| U1 | Error states not designed | ✅ Fixed | New artboard: filing failed, not understood, Redo, over budget |
| U2 | Corrections must be shown | ✅ Fixed | "Fixed · Groceries €42.00 → €24.00" with Undo |
| O4 | 5-second Redo | ✅ Fixed | Redo kept until the next capture (spec + artboard) |
| O5 | Undo targets 36pt tall | ✅ Fixed | Undo, Redo, Retry all 44pt tall |
| O6 | Swipe-only delete | ✅ Fixed in spec | Not drawable on a static canvas |
| P2 | Lists not marked up | ✅ Fixed except Capture (see M1) | |
| P3 | Progress bars exposed | ✅ Fixed | Hidden; text carries the values |
| P4 | Capture bar border 1.43:1 | ✅ Fixed | `#858E95` |
| P5 | Bubbles indistinguishable | ✅ Fixed | "You said: …" |

### Findings

#### Perceivable
| # | Issue | WCAG Criterion | Severity | Recommendation |
|---|-------|---------------|----------|----------------|
| M1 | On Capture, `role="log"` was put on the `<ol>` itself. That replaces its list role, so its four `<li>` items are list items with no list (axe: `listitem`, serious; `aria-allowed-role`). Introduced by the R2 fix. | 1.3.1 Info and Relationships | 🟡 Major | Wrap the list: `<div role="log" aria-live="polite" aria-label="…"><ol>…</ol></div>`. |
| m1 | At 200% zoom (195 px wide) rows on Capture, Pasted notes and Error states overflow sideways: long words in flex rows ("Accommodation", the three choice buttons) don't wrap. Passes at 320 px, the width WCAG 1.4.10 uses, so this is not an AA failure. | 1.4.4 Resize Text (advisory) | 🟢 Minor | Add `min-width: 0` to flex text children and `overflow-wrap: anywhere` on row text; let the choice buttons wrap. On a phone, verify with the largest system text size. |

#### Operable
| # | Issue | WCAG Criterion | Severity | Recommendation |
|---|-------|---------------|----------|----------------|
| m2 | The text field inside the capture bar is only 21 px tall, so tapping the bar's padding doesn't focus it; Paste and Dictate are squeezed to 42×44 by the flex row. (Target size is AAA in WCAG 2.1; this is platform guidance.) | 2.5.5 Target Size (AAA, advisory) | 🟢 Minor | Make the input fill the bar's height (44 px) and give the two buttons `flex-shrink: 0`. |
| m3 | Pasted-note items are named "Edit expense: flights, €148, …" while the visible text is "Flights · €148.00". Speech users saying what they see ("click Flights €148.00") may not match. | 2.5.3 Label in Name (A) | 🟢 Minor | Start the name with the visible text: "Flights, €148.00, Lisbon, Travel. Edit". |

#### Understandable
No issues found. Error states identify the problem in text and say what to do (3.3.1).

#### Robust
No issues found beyond M1. All controls expose a role, a name and (checkboxes) a state.

### Color Contrast Check
axe's `color-contrast` rule passed on every screen. New pairs from this round:

| Element | Foreground | Background | Ratio | Required | Pass? |
|---------|-----------|------------|-------|----------|-------|
| Checkbox outline, capture bar border, choice-button borders | #858E95 | #FFFFFF | 3.33:1 | 3:1 | ✅ |
| Same on page background | #858E95 | #F5F6F4 | 3.07:1 | 3:1 | ✅ |
| Error border, "€63 over" | #A84B0C | #FFFFFF | 5.71:1 | 4.5:1 | ✅ |
| Section labels (12px caps) | #5B636B | #F5F6F4 | 5.63:1 | 4.5:1 | ✅ |
| Focus ring | #1E6A86 | #F5F6F4 / #FFFFFF | 5.60 / 6.07:1 | 3:1 | ✅ |

### Keyboard Navigation (measured)
| Screen | Tab order | Space / Enter | Visible focus |
|---|---|---|---|
| Dashboard | 3 task checkboxes → Trip card → text field → Paste → Dictate | Space toggles a task ✅ | all 7 ✅ |
| Capture | Back → 3 Undo buttons (oldest first) → text field → Send | — | all 6 ✅ |
| Pasted notes | Back → Undo all → 6 items | — | all 8 ✅ |
| Trip | Back → 6 to-do checkboxes | Space toggles ✅ | all 7 ✅ |
| Error states | Retry → 3 choices → Redo | — | all 5 ✅ |

### Screen Reader (accessibility tree, measured)
| Element | Exposed as | Issue |
|---------|-------------|-------|
| Task | `checkbox "Check passport expiry Due today · for Lisbon"` | ✅ |
| Undo | `button "Undo expense €42 groceries"` | ✅ |
| Capture history | `log` containing orphaned `listitem`s | ❌ M1 |
| User message | `paragraph "You said: paid 42 for groceries…"` | ✅ |
| Filing error | `alert` with "Couldn't file this. Your words are saved…" and `button "Retry filing: …"` | ✅ |
| Trip card | `link "Lisbon trip, 13 to 16 March: €386 left of €600. …"` | ✅ |
| Month categories | `term` / `definition` pairs | ✅ |
| Pasted item | `button "Edit expense: flights, €148, …"` | ⚠️ m3 |

### Priority Fixes
1. **Wrap the capture list in the log region (M1)** — screen-reader users currently hear list items with no list; a two-line change.
2. **Let row text wrap at large text sizes (m1)** — keeps everything readable for people who enlarge text.
3. **Full-height text field and unsqueezed buttons (m2), visible-text-first names (m3)** — polish.

**Ready for a device test?** Yes for the design. The remaining risks are things only a real
build shows: announcements firing at the right moment, VoiceOver/TalkBack reading order,
and layout at the largest system text size.
