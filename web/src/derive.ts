// Figures the Dashboard shows, derived from the read cache, never stored (docs/spec.md):
// month spent = sum of expenses dated in the calendar month; left = budget − spent.

export type Task = { kind: "task"; id: number; ref: string; title: string; due_date: string | null;
  due_time: string | null; done: boolean };
export type Expense = { kind: "expense"; id: number; ref: string; amount_cents: number; date: string;
  category: string; description: string; trip_ref: string | null };
export type Trip = { kind: "trip"; id: number; ref: string; name: string; start_date: string;
  end_date: string; budget_cents: number | null };
export type Note = { kind: "note"; id: number; text: string };
export type Item = Task | Expense | Trip | Note;

export const MAX_TEXT = 4000;
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
  "September", "October", "November", "December"];
const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export function euros(cents: number): string {
  const whole = cents % 100 === 0;
  return new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR",
    minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: 2 }).format(cents / 100);
}

export function localDay(d: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function localDateTime(d: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${localDay(d)}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

export function monthName(day: string): string {
  return MONTHS[Number(day.slice(5, 7)) - 1];
}

export function headline(day: string): string {
  const d = new Date(`${day}T12:00:00`);
  return `${DAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

function addDays(day: string, n: number): string {
  const d = new Date(`${day}T12:00:00`);
  d.setDate(d.getDate() + n);
  return localDay(d);
}

export function tooLong(text: string): string | null {
  if (text.length <= MAX_TEXT) return null;
  const n = (x: number) => x.toLocaleString("en-US");
  return `Too long to file in one go: ${n(text.length)} of ${n(MAX_TEXT)} characters`;
}

export type Month = { name: string; spent: number; budget: number | null; left: number | null;
  over: boolean; ratio: number; top: { category: string; spent: number }[] };

export function month(items: Item[], today: string, budget: number | null): Month {
  const prefix = today.slice(0, 7);
  const expenses = items.filter((i): i is Expense => i.kind === "expense" && i.date.startsWith(prefix));
  const spent = expenses.reduce((s, e) => s + e.amount_cents, 0);
  const byCat = new Map<string, number>();
  expenses.forEach((e) => byCat.set(e.category, (byCat.get(e.category) || 0) + e.amount_cents));
  const top = [...byCat.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3)
    .map(([category, s]) => ({ category, spent: s }));
  const left = budget == null ? null : budget - spent;
  return { name: monthName(today), spent, budget, left, over: left != null && left < 0,
    ratio: budget ? Math.min(spent / budget, 1) : 0, top };
}

export type Due = Task & { state: "overdue" | "today" | "soon" };

export function dueSoon(items: Item[], today: string, limit = 5): { shown: Due[]; more: number } {
  const horizon = addDays(today, 7);
  const due = items
    .filter((i): i is Task => i.kind === "task" && !i.done && !!i.due_date && i.due_date <= horizon)
    .sort((a, b) => (a.due_date! + (a.due_time || "")).localeCompare(b.due_date! + (b.due_time || "")))
    .map((t) => ({ ...t, state: t.due_date! < today ? "overdue" : t.due_date === today ? "today" : "soon" } as Due));
  return { shown: due.slice(0, limit), more: Math.max(due.length - limit, 0) };
}

export function openTasks(items: Item[]): Task[] {
  return items.filter((i): i is Task => i.kind === "task" && !i.done);
}

export function activeTrip(items: Item[], today: string): (Trip & { spent: number }) | null {
  const trips = items.filter((i): i is Trip => i.kind === "trip" && i.end_date >= today)
    .sort((a, b) => a.start_date.localeCompare(b.start_date));
  const trip = trips[0];
  if (!trip) return null;
  const spent = items.filter((i): i is Expense => i.kind === "expense" && i.trip_ref === trip.ref)
    .reduce((s, e) => s + e.amount_cents, 0);
  return { ...trip, spent };
}

export function dueLabel(t: Due, today: string): string {
  if (t.state === "overdue") return "Overdue";
  const when = t.state === "today" ? "Today" : headline(t.due_date!).split(" ").slice(0, 3).join(" ");
  void today;
  return t.due_time ? `${when} ${t.due_time}` : when;
}

export function tripSpan(t: Trip): string {
  const s = new Date(`${t.start_date}T12:00:00`), e = new Date(`${t.end_date}T12:00:00`);
  const m = (d: Date) => MONTHS[d.getMonth()].slice(0, 3);
  return s.getMonth() === e.getMonth() ? `${s.getDate()}–${e.getDate()} ${m(e)}`
    : `${s.getDate()} ${m(s)} – ${e.getDate()} ${m(e)}`;
}
