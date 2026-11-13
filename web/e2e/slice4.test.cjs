// Slice 4 scenarios in a real browser against the real service (demo filer, throwaway Postgres).
// Each test signs in as its own user, so tests never see each other's data.
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const h = require("./harness.cjs");

let server, browser;
before(async () => { server = await h.startServer(); browser = await h.launch(); });
after(async () => { await browser?.close(); await server?.stop(); });

const expenses = (data) => data.items.filter((i) => i.kind === "expense");
const capturePosts = (page) => { const seen = []; page.on("request", (r) => { if (r.url().endsWith("/v1/captures")) seen.push(r); }); return seen; };

test("Scenario: a typed expense is filed against the month", async () => {
  const { page } = await h.newDevice(browser);
  await h.signIn(page, server.url, "u1@example.com");
  await h.seed(page, { monthly_budget_cents: 140000 });
  await h.send(page, "paid 42 for groceries");
  const row = page.locator(".filed-row", { hasText: "Expense €42 · Groceries · today" });
  await row.waitFor();
  assert.equal(await row.getByRole("button", { name: /^Undo/ }).count(), 1);
  const [e] = expenses(await h.changes(page));
  assert.deepEqual([e.amount_cents, e.category, e.date], [4200, "Groceries", await h.today(page)]);
  await page.getByRole("button", { name: "Back to dashboard" }).click();
  await page.getByText("€1,358 left").waitFor();
  await page.getByText("€42 spent of €1,400").waitFor();
});

test("Scenario: one sentence becomes two items", async () => {
  const { page } = await h.newDevice(browser);
  await h.signIn(page, server.url, "u2@example.com");
  await h.send(page, "paid 42 for groceries and book the car service");
  await page.locator(".filed-row", { hasText: "Book the car service" }).waitFor();
  const rows = page.locator(".entry").last().locator(".filed-row");
  assert.equal(await rows.count(), 2);
  assert.equal(await rows.getByRole("button", { name: /^Undo/ }).count(), 2);
  const data = await h.changes(page);
  const groceries = expenses(data).filter((e) => e.category === "Groceries");
  const tasks = data.items.filter((i) => i.kind === "task");
  assert.deepEqual(groceries.map((e) => e.amount_cents), [4200]);
  assert.deepEqual(tasks.map((t) => [t.title, t.due_date]), [["Book the car service", null]]);
});

test("Scenario: an expense without a date is filed as today", async () => {
  const { page } = await h.newDevice(browser);
  await h.signIn(page, server.url, "u3@example.com");
  await h.send(page, "coffee 3.50");
  await page.locator(".filed-row", { hasText: "Expense €3.50 · Eating out · today" }).waitFor();
  const [e] = expenses(await h.changes(page));
  assert.deepEqual([e.amount_cents, e.date], [350, await h.today(page)]);
});

test("Scenario: the monthly budget is set by saying it", async () => {
  const { page } = await h.newDevice(browser);
  await h.signIn(page, server.url, "u4@example.com");
  await h.send(page, "my budget is 1400 a month");
  await page.locator(".filed-row", { hasText: "Monthly budget €1,400" }).waitFor();
  await page.getByRole("button", { name: "Back to dashboard" }).click();
  await page.getByText("€1,400 left").waitFor();
  assert.match(await page.locator("#month-h").innerText(), /budget$/);
});

test("Scenario: dictated text is filed like typed text", async () => {
  const { page } = await h.newDevice(browser);
  await h.signIn(page, server.url, "u5@example.com");
  await page.getByRole("button", { name: "Dictate" }).click();          // focuses the field
  await page.keyboard.insertText("paid 42 for groceries");             // what the keyboard's dictation does
  await page.getByRole("button", { name: "Send" }).click();
  await page.locator(".filed-row", { hasText: "Expense €42 · Groceries" }).waitFor();
  const [e] = expenses(await h.changes(page));
  assert.deepEqual([e.amount_cents, e.category], [4200, "Groceries"]);
});

test("Scenario: capture that is not understood is kept as a note", async () => {
  const { page } = await h.newDevice(browser);
  await h.signIn(page, server.url, "u6@example.com");
  await h.send(page, "the thing with Marta");
  const row = page.locator(".filed-row", { hasText: "Saved as a note. Is it one of these?" });
  await row.waitFor();
  assert.ok(await row.locator(".suggestions .chip").count() <= 3);
  const data = await h.changes(page);
  assert.deepEqual(data.items.filter((i) => i.kind !== "note"), []);
});

test("Scenario: capture over 4,000 characters is not sent", async () => {
  const { page } = await h.newDevice(browser);
  await h.signIn(page, server.url, "u7@example.com");
  const posts = capturePosts(page);
  const box = page.getByRole("textbox", { name: "Tell me anything" });
  await box.fill("x".repeat(4001));
  await page.getByRole("button", { name: "Send" }).click();
  await page.getByText("Too long to file in one go: 4,001 of 4,000 characters").waitFor();
  assert.equal((await box.inputValue()).length, 4001);
  assert.equal(posts.length, 0);
});

test("Scenario: captures are filed in the order they were said", async () => {
  const { context, page } = await h.newDevice(browser);
  await h.signIn(page, server.url, "u8@example.com");
  await context.setOffline(true);
  await h.send(page, "paid 42 for groceries");
  await page.getByText(/Waiting to file/).first().waitFor();
  await h.send(page, "that was 24 not 42");
  await h.count(page.getByText(/Waiting to file/), 2);
  await context.setOffline(false);
  await page.locator(".filed-row", { hasText: "Expense €24 · Groceries" }).waitFor({ timeout: 30000 });
  const groceries = expenses(await h.changes(page)).filter((e) => e.category === "Groceries");
  assert.deepEqual(groceries.map((e) => e.amount_cents), [2400]);
});

test("Scenario: an item captured on the phone shows on the computer", async () => {
  const phone = await h.newDevice(browser, "phone");
  const computer = await h.newDevice(browser, "computer");
  await h.signIn(phone.page, server.url, "u9@example.com");
  await h.signIn(computer.page, server.url, "u9@example.com");
  await computer.page.getByText("€0 spent").waitFor().catch(() => {});
  await h.send(phone.page, "paid 42 for groceries");
  await phone.page.locator(".filed-row", { hasText: "Expense €42" }).waitFor();
  // the computer's tab comes to the front
  await computer.page.bringToFront();
  await computer.page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await computer.page.getByText("€42 spent").waitFor({ timeout: 5000 });
});

async function seedHousehold(page) {
  const day = await h.today(page);
  const month = day.slice(0, 8);
  const exps = Array.from({ length: 50 }, (_, i) => ({ amount_cents: 1000 + i, date: `${month}01`,
    category: ["Groceries", "Eating out", "Transport"][i % 3], description: `Item ${i + 1}` }));
  const soon = (n) => { const d = new Date(`${day}T12:00:00`); d.setDate(d.getDate() + n);
    return d.toISOString().slice(0, 10); };
  const tasks = Array.from({ length: 10 }, (_, i) => ({ title: `Task ${i + 1}`, due_date: soon(i % 7) }));
  const end = new Date(`${day}T12:00:00`); end.setDate(end.getDate() + 20);
  const start = new Date(`${day}T12:00:00`); start.setDate(start.getDate() + 10);
  await h.seed(page, { expenses: exps, tasks, monthly_budget_cents: 200000,
    trips: [{ name: "Lisbon", start_date: start.toISOString().slice(0, 10), end_date: end.toISOString().slice(0, 10), budget_cents: 60000 }] });
  return exps.reduce((s, e) => s + e.amount_cents, 0);
}

async function seesEverything(page, total) {
  const euros = new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR", minimumFractionDigits: total % 100 ? 2 : 0 }).format(total / 100);
  await page.getByText(`${euros} spent of €2,000`).waitFor();
  await page.getByRole("heading", { name: /^Lisbon/ }).waitFor();
  assert.equal(await page.locator(".tasks li").count(), 5);
  await page.getByText("+5 more").waitFor();
}

test("Scenario: signing in on a new device shows all data", async () => {
  const phone = await h.newDevice(browser, "phone");
  await h.signIn(phone.page, server.url, "u10@example.com");
  const total = await seedHousehold(phone.page);
  const fresh = await h.newDevice(browser, "computer");
  await h.signIn(fresh.page, server.url, "u10@example.com");
  await seesEverything(fresh.page, total);
});

test("Scenario: cleared website data comes back on the next sign-in", async () => {
  const { context, page } = await h.newDevice(browser, "phone");
  await h.signIn(page, server.url, "u11@example.com");
  const total = await seedHousehold(page);
  await page.reload();
  await seesEverything(page, total);
  // Safari clears the web app's stored data: cookies and IndexedDB
  await context.clearCookies();
  await page.evaluate(() => new Promise((r) => { const req = indexedDB.deleteDatabase("dumpit"); req.onsuccess = req.onerror = req.onblocked = () => r(); }));
  await page.reload();
  await page.getByLabel("Email").waitFor();
  await h.signIn(page, server.url, "u11@example.com");
  await seesEverything(page, total);
});

test("Scenario: an old sign-in link does not sign anyone in (the page offers a new link)", async () => {
  const { page } = await h.newDevice(browser);
  await page.goto(`${server.url}/v1/auth/callback?t=not-a-real-token`);
  await page.getByText("That sign-in link has expired or was already used").waitFor();
  await page.getByRole("button", { name: "Send a new link" }).waitFor();
});

test("Scenario: signing out a lost device ends its access (it shows the sign-in screen)", async () => {
  const phone = await h.newDevice(browser, "phone");
  const laptop = await h.newDevice(browser, "computer");
  await h.signIn(phone.page, server.url, "u12@example.com");
  await h.signIn(laptop.page, server.url, "u12@example.com");
  await phone.page.getByRole("button", { name: "Devices and sign-out" }).click();
  await phone.page.getByRole("button", { name: /^Sign out (?!this)/ }).click();
  await h.count(phone.page.getByRole("button", { name: /^Sign out/ }), 1);
  await laptop.page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await laptop.page.getByLabel("Email").waitFor({ timeout: 5000 });
});
