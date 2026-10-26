## Accessibility Audit: Dumpit v1 Mockup (Dashboard, Capture, Pasted notes, Trip)
**Standard:** WCAG 2.1 AA | **Date:** 25 October 2026

**Scope and method.** The four 390×844 artboards on the "Dumpit v1 Mockup" canvas, audited
from their source markup and colour values, plus the proposed states in the handoff spec
(`docs/handoff.md`). Contrast ratios are computed with the WCAG relative-luminance
formula. **Not done:** no screen-reader or switch-access testing on a device, and no automated
scanner run. The mockup is static, so behaviour (announcements, focus movement) is audited
against what the markup and handoff specify, not observed. Test with VoiceOver/TalkBack once
there is a build.

### Summary
**Issues found:** 16 | **Critical:** 2 | **Major:** 7 | **Minor:** 7

All text colours pass. The serious problems are structural: the capture input hides its
focus ring, and task checkboxes are drawn as decorative shapes that a keyboard or screen
reader cannot use.

### Findings

#### Perceivable
| # | Issue | WCAG Criterion | Severity | Recommendation |
|---|-------|---------------|----------|----------------|
| P1 | Unchecked task checkbox outline `#9AA2A9` is 2.59:1 on white; it is the only thing showing a checkbox is there. | 1.4.11 Non-text Contrast | 🟡 Major | Use `#858E95` (3.33:1 on white, 3.07:1 on the page background) or darker for `color-check-idle`. |
| P2 | Filed items, trip to-dos, trip spending and the "Due soon" tasks are visually lists but marked up as stacked `<div>`s. | 1.3.1 Info and Relationships | 🟢 Minor | Mark each as a list (`<ul>`/`<li>`, or the platform list role) so a screen reader says "list, 6 items". |
| P3 | Progress bars are plain shapes with no text alternative. The figures beside them carry the same information. | 1.1.1 Non-text Content | 🟢 Minor | Hide the bars from assistive tech (`aria-hidden="true"`), since the text already says "€488 left · €912 spent". If kept exposed, give them `role="progressbar"` with values. |
| P4 | Capture bar border `#D4D9D5` is 1.43:1 on white and 1.32:1 on the page. The field is still identifiable by its placeholder and buttons, so this is borderline. | 1.4.11 Non-text Contrast | 🟢 Minor | Darken to `#858E95` or rely on a stronger fill difference; confirm with users with low vision. |
| P5 | User messages in the Capture log are distinguished from the app's replies only by position and bubble colour. | 1.3.1 Info and Relationships | 🟢 Minor | Prefix bubbles for assistive tech: "You said: paid 42 for groceries…"; label filed rows "Filed:". |

#### Operable
| # | Issue | WCAG Criterion | Severity | Recommendation |
|---|-------|---------------|----------|----------------|
| O1 | Both capture inputs set `outline: none` and nothing replaces it. On Capture the 2px accent border looks like focus but is static, not tied to focus. | 2.4.7 Focus Visible | 🔴 Critical | Remove `outline: none`; draw the 2px accent border on the bar with `:focus-within` (or the native focus state), and keep a visible focus ring on every control. |
| O2 | Task checkboxes are `<span>` shapes: not focusable, not operable by keyboard or switch, no checked state. | 2.1.1 Keyboard; 4.1.2 Name, Role, Value | 🔴 Critical | Build as real checkboxes (native control or `role="checkbox"` + `aria-checked`), labelled by the task title and due date, with the 18pt visual padded to a 44pt target. |
| O3 | Every Undo button is named only "Undo". In the Capture log there are several, so out of context (rotor, voice control) they are indistinguishable. | 2.4.6 Headings and Labels; 2.4.4 Link Purpose | 🟡 Major | Accessible names with the item: "Undo expense €42 groceries", "Undo move dentist to Friday". Keep the visible label "Undo". |
| O4 | The handoff proposes Redo for only 5 seconds after an undo. | 2.2.1 Timing Adjustable | 🟢 Minor | Keep Redo available until the next capture, or leave the undone row in the log with a Redo button. Undo itself already persists. |
| O5 | Undo buttons are 64×36 and trip to-do rows 36pt tall. (The 44×44 rule, 2.5.5, is Level AAA in WCAG 2.1, so this is not an AA failure; it is the platform guideline on iOS and Android.) | 2.5.5 Target Size (AAA, advisory) | 🟢 Minor | Pad hit areas to 44pt, as the handoff already specifies. |
| O6 | Swipe-left-to-delete on tasks (proposed in the handoff) has no stated non-gesture route. | 2.1.1 Keyboard (and 2.5.1 Pointer Gestures for multi-point; single swipe is fine but needs a keyboard route) | 🟡 Major | Provide Delete in the item's edit sheet and as an accessibility custom action. |

#### Understandable
| # | Issue | WCAG Criterion | Severity | Recommendation |
|---|-------|---------------|----------|----------------|
| U1 | No error states are designed: a filing failure, a capture it did not understand, and an over-budget month are proposed in the handoff but not drawn. | 3.3.1 Error Identification | 🟡 Major | Design them before build, each saying what happened and what to do in text ("Couldn't file this. Retry."), not by colour alone. |
| U2 | Corrections like "that was 24 not 42" change the most recent matching item without saying which one before it happens. That is by design, but the result must be stated. | 3.3.4 Error Prevention (AA for financial data) | 🟡 Major | The "FIXED · Groceries €42.00 → €24.00" row with Undo meets this if it is always shown and announced. Make that a requirement, and never apply a correction silently. |

#### Robust
| # | Issue | WCAG Criterion | Severity | Recommendation |
|---|-------|---------------|----------|----------------|
| R1 | The Dictate control is a link (`<a href>`) that in the app would start dictation. A screen reader announces "link", which predicts navigation. | 4.1.2 Name, Role, Value | 🟡 Major | Make it a button. Same for any control that acts rather than navigates. |
| R2 | Nothing announces the result of a capture: filed items, "waiting to file" and undo appear silently. | 4.1.3 Status Messages | 🟡 Major | Announce politely (live region / accessibility announcement): "Filed: expense €42, groceries." "Saved. Will file when you're back online." "Undone." |
| R3 | The whole Trip card is one link whose accessible name is all of its text (about 25 words). | 2.4.4 Link Purpose | 🟢 Minor | Name it "Lisbon trip, 13 to 16 March, €386 left of €600" and hide the inner text from the link name. |

(R2's severity sits with Major rather than Critical only because the mockup is static; in a
build it is the main way a blind user learns the app did anything.)

### Color Contrast Check
| Element | Foreground | Background | Ratio | Required | Pass? |
|---------|-----------|------------|-------|----------|-------|
| Primary text | #15181C | #FFFFFF | 17.81:1 | 4.5:1 | ✅ |
| Primary text on page | #15181C | #F5F6F4 | 16.43:1 | 4.5:1 | ✅ |
| User bubble text | #15181C | #E4EFF3 | 15.21:1 | 4.5:1 | ✅ |
| Muted meta (12–13px) | #5B636B | #FFFFFF | 6.10:1 | 4.5:1 | ✅ |
| Muted meta on page | #5B636B | #F5F6F4 | 5.63:1 | 4.5:1 | ✅ |
| Pasted note (mono) | #3E454C | #FFFFFF | 9.72:1 | 4.5:1 | ✅ |
| Accent text / Undo | #1E6A86 | #FFFFFF | 6.07:1 | 4.5:1 | ✅ |
| TRIP tag (11px bold) | #1E6A86 | #E4EFF3 | 5.18:1 | 4.5:1 | ✅ |
| SPENT / FIXED tag (11px bold) | #2F6B4F | #E5F1EA | 5.42:1 | 4.5:1 | ✅ |
| Due today / overdue | #A84B0C | #FFFFFF | 5.71:1 | 4.5:1 | ✅ |
| Icon on accent button | #FFFFFF | #1E6A86 | 6.07:1 | 3:1 | ✅ |
| Input placeholder (browser default) | ≈#757575 | #FFFFFF | 4.61:1 | 4.5:1 | ✅ (barely — set it explicitly to `color-text-muted`) |
| Checkbox outline (idle) | #9AA2A9 | #FFFFFF | 2.59:1 | 3:1 | ❌ |
| Capture bar border | #D4D9D5 | #FFFFFF | 1.43:1 | 3:1 | ❌ (borderline, see P4) |
| Progress fill vs track | #1E6A86 | #E3E6E3 | 4.82:1 | 3:1 | ✅ |
| Card borders, track vs white | #E3E6E3 | #FFFFFF | 1.26:1 | — | n/a (decorative) |
| "Not in v1" dashed outline | #B9C0C5 | #F5F6F4 | 1.70:1 | — | n/a (decorative; remove before release) |

**Alternate accents** from the canvas Tweaks all pass as text on white (#3D5A80 7.06, #2F6B4F
6.29, #8A4B2D 6.72), on the soft tag fill, and as progress fills against the track (≥5.0).

**Correction to the handoff spec:** it says contrast passes throughout. That is true for text
but not for non-text UI: the checkbox outline (P1) fails 1.4.11.

### Keyboard Navigation
Expected behaviour for the build; the mockup supports only the native `<button>`, `<a>` and
`<input>` elements it contains.

| Element | Tab Order | Enter/Space | Escape | Arrow Keys |
|---------|-----------|-------------|--------|------------|
| Task checkbox (Dashboard, Trip) | After its card heading, one stop per task | Space toggles done | — | — |
| Trip card | After the budget card | Enter opens Trip | — | — |
| Capture input | Last content stop before its buttons | Enter sends; Shift+Enter new line | Clears focus (keeps text) | Move cursor |
| Paste button | After input | Activates paste | — | — |
| Dictate button | After Paste | Starts dictation | Stops dictation | — |
| Send button (Capture) | After input | Sends | — | — |
| Undo (each filed row) | In log order, oldest to newest | Undoes that item | — | — |
| Undo all (Paste) | After the "Filed 6 items" heading | Undoes all | — | — |
| Back button | First stop on sub-screens | Returns to Dashboard | Same as Back (*proposed*) | — |
| Edit sheet (*proposed*) | Focus moves into it on open; trapped until closed | Saves | Closes, focus returns to the row | — |

### Screen Reader
| Element | Announced As (as built in the mockup) | Issue |
|---------|-------------|-------|
| Task checkbox | Nothing; skipped | O2: not exposed |
| Task row | "Check passport expiry. Today · for Lisbon" | Fine once the checkbox carries it |
| Paste button | "Paste notes, button" | ✅ |
| Dictate control | "Dictate, link" | R1: should be button |
| Capture input | "Tell it anything, text field" | ✅ (visually hidden label present) |
| Undo | "Undo, button" ×3 on Capture | O3: ambiguous |
| Filed row tag | "SPENT €42.00 · Groceries · today" | Reads "SPENT" letter-cased oddly on some readers; set the accessible text to "Spent" |
| Progress bar | Nothing | P3: fine if hidden deliberately |
| Trip card | ~25-word link name | R3: too long |
| Result of a capture | Nothing | R2: no status message |
| Day-by-day placeholder | "Day-by-day plan. Not in v1 · planned for Phase 3" | Remove before release |

### Priority Fixes
1. **Restore a visible focus indicator on the capture input (O1)** — affects keyboard and switch users, who otherwise lose track of where they are on the app's main control.
2. **Build task checkboxes as real checkboxes (O2)** — blocks keyboard, switch and screen-reader users from completing tasks at all.
3. **Announce capture results (R2) and give each Undo a specific name (O3)** — without these a blind user cannot tell what was filed or which item an Undo affects, which defeats the "notice a mistake" design.
4. **Darken the checkbox outline to `#858E95` (P1)** — low-vision users may not see empty checkboxes.
5. **Make Dictate a button (R1), add a non-swipe Delete (O6), design the error states (U1) and always show corrections (U2)**.
6. **Minor:** list semantics, progress bars hidden, shorter trip-card name, user-bubble prefix, Redo window, 44pt hit areas, capture-bar border.

**Text resize and reflow** (1.4.4 / 1.4.10) can't be judged from fixed-size frames. The
handoff's dynamic-type rules (stack the 3-column grids, nothing clips at 200%) are the
requirement; verify on device at the largest text size.
