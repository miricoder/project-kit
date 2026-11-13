import { describe, expect, it } from "vitest";
import { activeTrip, dueSoon, euros, month, tooLong, type Item } from "./derive";

const e = (id: number, cents: number, date: string, category = "Groceries", trip_ref: string | null = null): Item =>
  ({ kind: "expense", id, ref: `e${id}`, amount_cents: cents, date, category, description: "x", trip_ref });

describe("month figures", () => {
  it("left is budget minus this month's spending", () => {
    const m = month([e(1, 4200, "2026-02-23"), e(2, 999, "2026-01-31")], "2026-02-23", 140000);
    expect([m.name, m.spent, m.left, m.over]).toEqual(["February", 4200, 135800, false]);
    expect(euros(m.left!)).toBe("€1,358");
  });
  it("says how much over", () => {
    const m = month([e(1, 150000, "2026-02-01")], "2026-02-23", 140000);
    expect([m.over, euros(-m.left!), m.ratio]).toEqual([true, "€100", 1]);
  });
  it("top three categories", () => {
    const items = [e(1, 100, "2026-02-01", "A"), e(2, 300, "2026-02-01", "B"), e(3, 200, "2026-02-01", "C"), e(4, 50, "2026-02-01", "D")];
    expect(month(items, "2026-02-10", null).top.map((t) => t.category)).toEqual(["B", "C", "A"]);
  });
  it("formats cents", () => {
    expect([euros(350), euros(4200), euros(140000)]).toEqual(["€3.50", "€42", "€1,400"]);
  });
});

describe("capture length", () => {
  it("4,000 characters is fine and 4,001 is not", () => {
    expect(tooLong("x".repeat(4000))).toBeNull();
    expect(tooLong("x".repeat(4001))).toBe("Too long to file in one go: 4,001 of 4,000 characters");
  });
});

describe("dashboard lists", () => {
  it("due soon is overdue, today and the next week, at most five", () => {
    const t = (id: number, due: string | null, done = false): Item =>
      ({ kind: "task", id, ref: `t${id}`, title: `T${id}`, due_date: due, due_time: null, done });
    const items = [t(1, "2026-02-20"), t(2, "2026-02-23"), t(3, "2026-03-10"), t(4, null), t(5, "2026-02-24", true),
      t(6, "2026-02-25"), t(7, "2026-02-26"), t(8, "2026-02-27"), t(9, "2026-02-28")];
    const due = dueSoon(items, "2026-02-23");
    expect(due.shown.map((d) => [d.id, d.state])).toEqual([[1, "overdue"], [2, "today"], [6, "soon"], [7, "soon"], [8, "soon"]]);
    expect(due.more).toBe(1);
  });
  it("the active trip is the current or next one, with its spending", () => {
    const trip = (id: number, s: string, en: string): Item => ({ kind: "trip", id, ref: `p${id}`, name: `P${id}`, start_date: s, end_date: en, budget_cents: null });
    const items = [trip(1, "2026-01-01", "2026-01-05"), trip(2, "2026-03-13", "2026-03-15"), e(9, 1200, "2026-02-01", "Travel", "p2")];
    expect(activeTrip(items, "2026-02-23")).toMatchObject({ ref: "p2", spent: 1200 });
  });
});
