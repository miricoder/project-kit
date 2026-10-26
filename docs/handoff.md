# Handoff Spec: Dumpit v1 — Dashboard, Capture, Pasted notes, Trip

> Source: the "Dumpit v1 Mockup" canvas (https://claude.ai/artifact/YKwgxHfyNuYxb46JVZHYBL),
> four static 390×844 phone screens. Scope is bound by `docs/proposal.md` (v1 = Phases 0–2).
>
> **Status of this spec.** Values marked *measured* are taken from the mockup. Everything marked
> *proposed* (most states, motion, dark mode, error copy) was not drawn and is a recommendation
> to confirm with design before build. The phone platform (iOS or Android) is still undecided,
> so components are described by behaviour, not by framework.

---

### Overview

One person tells the app their life admin in passing — typed, dictated with the phone's
keyboard mic, or pasted — and the app files it as tasks, expenses and trips without asking
them to choose a category or list. The four screens are:

| Screen | Job | Reached from |
|---|---|---|
| **Dashboard** | Glance: what's due, how the month's money stands, the active trip. Capture bar always at the bottom. | App launch |
| **Capture & undo** | The running log of what you said and what it filed, each with Undo. Corrections are typed here ("that was 24 not 42"). | Sending from the capture bar; tapping the mic |
| **Pasted notes** | A pasted block of messy text and the items it became, with Undo all. | Paste button in the capture bar |
| **Trip** | One trip: budget / spent / left, backward-scheduled to-dos, trip spending. | Trip card on the Dashboard |

**The design rule behind every screen:** the app does the filing, and the person only ever has
to *notice* a mistake, never *prevent* one. Hence one-line confirmations with Undo after every
capture instead of a review form. Do not add confirmation dialogs or category pickers to the
capture path; that breaks the product's core promise (research, "the one thing").

---

### Layout

| Property | Value | Notes |
|---|---|---|
| Design frame | 390 × 844 pt | *measured*. One column, no grid. |
| Side gutter | `space-gutter` 20 | *measured* |
| Top padding | 28 (20 frame + 8 header) | *measured*; sits **below** the OS safe-area inset — the mockup has no status bar |
| Bottom padding | 16 | *measured*; sits **above** the home-indicator safe area |
| Vertical rhythm | `space-section` 14 between blocks | *measured* |
| Capture bar | pinned to bottom of the Dashboard and Capture screens; content scrolls behind it | *proposed*: mockup uses `margin-top:auto`; in a real build the list scrolls and the bar stays put, rising with the keyboard |

Screen headers (Capture, Paste, Trip) = 44×44 back button (pulled 10pt into the gutter so the
chevron aligns with the gutter) + title, 8pt apart.

---

### Design Tokens Used

Names are proposed; the values are measured from the mockup unless marked.

**Colour**

| Token | Value | Usage |
|---|---|---|
| `color-bg` | #F5F6F4 | Screen background |
| `color-surface` | #FFFFFF | Cards, rows, capture bar |
| `color-text` | #15181C | Primary text, icons |
| `color-text-muted` | #5B636B | Meta lines, labels, captions (6.1:1 on white) |
| `color-border` | #E3E6E3 | Card borders, progress track |
| `color-divider` | #EEF0EE | Row dividers inside a card; neutral tag and secondary button fill |
| `color-border-strong` | #858E95 | Capture bar border (idle), secondary button borders. Was #D4D9D5 (1.43:1); changed for WCAG 1.4.11 |
| `color-check-idle` | #858E95 | Unchecked checkbox outline, "waiting to file" dashed border (3.33:1 on white). Was #9AA2A9 (2.59:1, failed 1.4.11) |
| `color-placeholder` | #B9C0C5 | Dashed "not in v1" outline |
| `color-accent` | #1E6A86 | Primary actions, progress fill, Undo, focused capture bar border, "left" figures |
| `color-accent-hover` | #154C60 | Link hover / pressed (from mockup `a:hover`) |
| `color-accent-soft` | #E4EFF3 | User's message bubbles, TRIP tag fill |
| `color-spent` | #2F6B4F on `color-spent-soft` #E5F1EA | SPENT / FIXED tags |
| `color-warn` | #A84B0C | Overdue / due-today text and checkbox outline (5.4:1 on white) |
| `color-on-accent` | #FFFFFF | Icons on accent buttons |

The accent is a designer tweak (alternates drawn: #3D5A80, #2F6B4F, #8A4B2D). Build it as one
token so it can change in one place.

**Typography** — family `Manrope` (Google Fonts, weights 400/500/600/700), fallback system UI.

| Token | Size / weight | Usage |
|---|---|---|
| `font-title-lg` | 26 / 700, tracking −0.02em | Dashboard headline |
| `font-title` | 20 / 700 | Screen titles; trip budget figures |
| `font-figure-lg` | 28 / 700, tracking −0.02em | Month "€488 left" |
| `font-figure` | 22 / 700 | Trip card "€386" |
| `font-heading` | 15 / 700 | Card headings ("Due soon") |
| `font-item` | 15 / 600 | Task titles, capture input, bubble text (15/400) |
| `font-row` | 14 / 400–600 | Filed-item rows, trip to-dos, Undo (14/700) |
| `font-meta` | 13 / 400–600 | Dates, "left · spent" lines |
| `font-caption` | 12 / 400–700 | Secondary meta, category labels |
| `font-tag` | 11 / 700, tracking 0.04em, uppercase **via text-transform** | Item-kind tags. Write the text in sentence case ("Spent") so screen readers don't spell it out |
| `font-mono` | 13 / 400, line-height 1.5, system monospace | Pasted note echo |

Respect the OS text-size setting (*proposed*): scale every token; at the two largest sizes, let
figure rows wrap and stack the 3-column grids into one column.

**Spacing, radius, size**

| Token | Value | Usage |
|---|---|---|
| `space-gutter` | 20 | Screen side padding |
| `space-section` | 14 | Gap between cards/blocks |
| `space-card-x` / `space-card-y` | 16 / 14 (12 on Trip lists) | Card padding |
| `space-row-gap` | 10 | Checkbox → text; rows inside "Due soon" |
| `space-inline` | 8 | Tag → text; icon → label |
| `radius-card` | 16 | Cards |
| `radius-row` | 12 | Filed-item containers, pasted-note box, back button |
| `radius-bubble` | 16 16 4 16 | User message bubble (tail bottom-right) |
| `radius-capture` | 22 | Capture bar |
| `radius-button` | 14 | Mic / paste / send buttons |
| `radius-tag` / `radius-check` | 6 | Kind tags, checkboxes |
| `size-touch` | 44 | Minimum hit target, every control |
| `size-check` | 18 | Checkbox (hit area padded to 44) |
| `progress-height` | 8, radius 4 | Budget bars |
| `shadow-capture` | 0 2 10 rgba(21,24,28,.06) | Capture bar on Dashboard only |

---

### Components

| Component | Variants | Props | Notes |
|---|---|---|---|
| **CaptureBar** | `idle`, `focused` (driven by the field's real focus, never drawn statically) | `value`, `placeholder`, `onSend`, `onPaste`, `onDictate` | Idle: 1pt `color-border-strong` + shadow; paste button (neutral) + mic button (accent, a **button**, not a link). Focused: `color-accent` border plus a 2pt accent ring on the whole bar (the field's own outline may be hidden only because the bar shows this), and a **Send** arrow replaces paste+mic once there is text. Placeholder: "Tell me anything… “paid 42 for groceries”". Multi-line: grows to 5 lines, then scrolls inside. |
| **Card** | default, `link` (Trip card) | `title`, `meta`, `children`, `href?` | Link variant is one tap target for the whole card. |
| **TaskRow** | `idle`, `due-today`/`overdue`, `done` | `title`, `meta`, `state`, `onToggle` | A **real checkbox** (native control) with the whole row as its label, so its name is title + due date. Due/overdue: checkbox outline and meta in `color-warn`, meta bold. Done: filled accent check with white tick, title muted + strikethrough. |
| **BudgetSummary** | `month`, `trip-card`, `trip-header` | `budget`, `spent`, `currency` | "left" = budget − spent. Bar fill = spent ÷ budget, clamped to 100%. Month shows top 3 categories by spend. |
| **ProgressBar** | `normal`, `over-budget` (*proposed*) | `ratio` | Over budget: full bar in `color-warn` and "€X over" replaces "left". |
| **KindTag** | `TRIP`, `TASKS`/`TASK`, `SPENT`, `MOVED`, `FIXED` | `kind` | TRIP = accent-soft/accent; SPENT, FIXED = spent-soft/spent; TASK(S), MOVED = divider/text. |
| **FiledRow** | `with-undo`, `summary` (no undo), `two-line` (Paste, tappable to edit) | `kind`, `text`, `subtext?`, `onUndo?`, `undoLabel` | 48pt min height (52 for two-line). Undo is a 64×44 text button whose accessible name names the item ("Undo expense €42 groceries"). Rows sit in a list. |
| **MessageBubble** | user | `text` | Right-aligned, max 80% width. |
| **PendingRow** | `waiting` | `text` | Dashed `color-check-idle` border, clock icon: "Waiting to file · you were offline". |
| **PlaceholderCard** | — | — | Removed from the Trip screen; now a sticky note on the canvas. Not part of the product. |
| **BackButton** | — | `onBack` | 44×44, chevron, `aria-label="Back to dashboard"`. |

Icons are 2pt-stroke line icons (mic, clipboard, plane, send-arrow, chevron, clock, info, check).
Use the platform's equivalent set at 18–22pt.

---

### States and Interactions

| Element | State | Behavior |
|---|---|---|
| Capture bar | Empty | Paste + mic shown; Send hidden. |
| Capture bar | Has text | Send replaces paste + mic. Return key = send; Shift/long-press return = new line (*proposed*). |
| Capture bar | Sending | Text moves into a user bubble immediately; a "Filing…" row with a small spinner appears under it; input clears and stays focused. |
| Capture bar | Sent, filed | "Filing…" row is replaced by FiledRows (one per item). |
| Capture bar | Offline | Bubble + PendingRow "Waiting to file · you were offline". Files automatically on reconnect, then the PendingRow becomes FiledRows. Proposal criterion: within 30s of reconnecting. |
| Capture bar | Filing failed (server/model error) | Row with a 2pt `color-warn` border, alert icon and text "Couldn't file this. Your words are saved; nothing was lost." + **Retry**. Announced as an alert. Drawn on "Error & edge states". |
| Capture bar | Not understood | "Saved as a note. Is it one of these?" + **It's an expense, €20** / **Make it a task** / **Leave as a note**. The one place a choice is offered, and only after the fact. Drawn on "Error & edge states". |
| Mic button | Tap | Starts OS dictation into the input (v1 uses the keyboard's dictation, no custom recorder). |
| Paste button | Tap | Pastes clipboard into the input and opens the Pasted notes view on send. Empty clipboard: button disabled (40% opacity). |
| Undo | Tap | Reverts that one item; the row text becomes struck through + "Undone" and Undo becomes **Redo**, which stays until the next capture (no time limit, WCAG 2.2.1). Drawn on the "Error & edge states" artboard. |
| Undo all (Paste) | Tap | Reverts every item from that paste; same Redo window. |
| FiledRow / pasted item | Tap | *proposed*: opens an inline edit sheet with the item's fields (amount, date, category, trip). Typing a correction in the capture bar is the primary way; the sheet is the fallback. |
| TaskRow checkbox | Tap | Toggles done; row animates to done state; done tasks leave "Due soon" after 3s. |
| TaskRow | Swipe left | *proposed*: Delete (destructive, with Undo snackbar). **Also** available without a gesture: Delete in the edit sheet and as an accessibility custom action. |
| Trip card | Tap / pressed | Opens Trip; pressed = surface tint `color-divider`. |
| Back button | Tap / OS back gesture | Returns to Dashboard. |
| Links, accent text | Pressed | `color-accent-hover`. (Hover only matters on tablet/pointer.) |
| Dashboard | Pull down | *proposed*: refresh (re-run any pending filings). |

---

### Responsive Behavior

Phone only in v1 (proposal: one phone platform, no tablet or web).

| Breakpoint | Changes |
|---|---|
| Large phone (≥ 428 wide) | Same layout; cards stretch; content max-width 480, centred. |
| Base (375–427) | As drawn. |
| Small phone (320–374) | Gutter 16; Dashboard headline 22; month category grid stays 3 columns but values may wrap; capture bar keeps both buttons. |
| Landscape | Supported, single column, max-width 560 centred. Capture bar stays pinned. |
| Large text sizes | 3-column grids (month categories, trip budget) become stacked rows. |
| Keyboard open | Capture bar rides on top of the keyboard; the log scrolls to the newest entry. |

---

### Edge Cases

- **Empty state (first launch):** Dashboard shows no cards, only a short line above the capture bar: "Tell it anything — a payment, a plan, a reminder. It'll sort it out." plus three tappable examples that fill the input. No budget card until a monthly budget exists ("Set a monthly budget by saying it: ‘my budget is 1400 a month’").
- **No active trip:** trip card hidden (not an empty card).
- **Nothing due:** "Due soon" card shows "Nothing due this week." in `color-text-muted`.
- **Many tasks:** "Due soon" shows at most 5, then "+N more" link to a full list (*proposed* list screen; not in the mockup).
- **Long text:** task titles wrap to 2 lines then truncate with an ellipsis; FiledRow text wraps (never truncates — the user must see exactly what was filed); bubbles wrap fully; trip names truncate at 1 line in the card, 2 in the header.
- **Large amounts:** format with locale separators (€1,400 / 1.400 €); figures shrink one step above 7 characters rather than wrapping.
- **Over budget:** see ProgressBar `over-budget`.
- **Long pasted notes:** echo box shows the first 8 lines with "Show all"; filed list is unlimited and scrolls.
- **Slow connection:** "Filing…" row persists; after 10s it reads "Still filing — slow connection"; capture never blocks typing the next item.
- **Missing data:** an expense without a date files as today; a task without a date files undated (listed under "Someday", *proposed*); a trip without a budget shows "No budget set" in place of the figures.
- **International text:** layout must survive +35% string length (German, Portuguese); no fixed-width labels. Tags (SPENT etc.) are fixed English in the mockup and must be localised (allow up to 10 characters).
- **Currency:** one home currency in v1 (assumed EUR). Amounts in another currency are not converted; spec the tag to show the home currency only.

---

### Animation / Motion

All *proposed*; the mockup is static. Respect the OS "reduce motion" setting by replacing every
movement with a 150ms fade.

| Element | Trigger | Animation | Duration | Easing |
|---|---|---|---|---|
| User bubble | Send | Slides up 8pt + fades in from the capture bar | 200ms | ease-out |
| Filed rows | Filing completes | Fade in, staggered 40ms per row | 180ms | ease-out |
| Undo | Tap | Strikethrough draws left→right | 150ms | ease-in-out |
| Checkbox | Toggle done | Fill + tick scale 0.8→1 | 160ms | spring (damping 0.7) |
| Progress bar | Value change | Width animates | 300ms | ease-in-out |
| PendingRow → FiledRow | Reconnect | Cross-fade | 200ms | linear |
| Screen push (Trip, Capture) | Navigate | Platform default push | platform | platform |

---

### Accessibility Notes

- **Contrast:** all text pairs pass AA (muted 6.10:1, warn 5.71:1, accent 6.07:1 on white). Non-text UI must reach 3:1: checkbox outlines and the capture-bar border use `#858E95` (3.33:1). All four accent options pass as text, on tag fills, and as progress fills.
- **Colour is never the only signal:** due/overdue rows also say "Today"/"Overdue" in words; tags carry text labels; budget state says "left"/"over".
- **Focus order — Dashboard:** headline → Due soon (each task: checkbox, then title) → February budget → Trip card → capture input → Paste → Dictate.
  **Capture:** Back → log oldest→newest (each bubble, then its rows and Undo buttons) → input → Send.
  **Paste:** Back → pasted note → "Filed 6 items" heading → Undo all → each item → tip.
  **Trip:** Back → title/dates → budget summary → each to-do → spending list.
- **Labels:** icon buttons need `aria-label`/accessibility labels — "Paste notes", "Dictate", "Send", "Back to dashboard". Checkboxes are real checkboxes labelled by the task title ("Check passport expiry, due today, not done"). Progress bars are decorative (hidden); the text beside them carries the values.
- **Undo buttons** need context: "Undo expense €42 groceries", not just "Undo".
- **The capture log is a live log region** (`role="log"`, polite), and each user bubble carries a hidden "You said:" prefix.
- **Progress bars are hidden from assistive tech**; the adjacent text carries the values. The Trip card link has a short name: "Lisbon trip, 13 to 16 March: €386 left of €600".
- **Announcements:** after a capture is filed, announce politely: "Filed: expense €42, groceries. Moved: dentist to Friday 27 February." On undo: "Undone." On offline: "Saved. Will file when you're back online."
- **Touch targets:** every control ≥ 44×44 (checkboxes and Undo padded out to 44).
- **Keyboard / switch access:** everything reachable without gestures; swipe-to-delete has an equivalent in the edit sheet.
- **Dynamic type:** see Typography; nothing clips at 200%.

---

### Open questions for design

1. Dark mode is not drawn. (Error states, Redo and over-budget are now drawn on the "Error & edge states" artboard.) Needed for v1? (Tokens are set up to make it a palette swap.)
2. Edit sheet, full task list and first-launch empty state are proposed here but not drawn.
3. Monthly budget setup flow isn't drawn (assumed: said in the capture bar).
4. Platform choice (iOS/Android) changes navigation, haptics and notification styling.
5. Remove the "Day-by-day plan · not in v1" placeholder card before build, or keep as a teaser?
