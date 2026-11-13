// Slice 15 scenarios in a real browser: the update notice, the "new version" offer and the
// version on the Devices screen. The test build is version 0.2.0 (scripts/test.sh) and the
// server reads tests/fixtures/changelog.md, which has 0.1.0, 0.2.0 and 0.3.0.
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const h = require("./harness.cjs");

let server, browser;
before(async () => { server = await h.startServer(); browser = await h.launch(); });
after(async () => { await browser?.close(); await server?.stop(); });

/** What the device remembers as the version it last ran (as an older app would have left it). */
const setSeen = (page, version) => page.evaluate((v) => new Promise((resolve, reject) => {
  const req = indexedDB.open("dumpit");
  req.onsuccess = () => {
    const tx = req.result.transaction("meta", "readwrite");
    tx.objectStore("meta").put(v, "seen_version");
    tx.oncomplete = () => { req.result.close(); resolve(); };
    tx.onerror = () => reject(tx.error);
  };
  req.onerror = () => reject(req.error);
}), version);

/** Deploy a different version, as far as the server is concerned. */
const deploy = (page, version) => page.evaluate(async (v) => {
  const res = await fetch("/__version", { method: "POST", body: JSON.stringify({ version: v }),
    headers: { "Content-Type": "application/json" } });
  if (res.status !== 200) throw new Error(`deploy failed: ${res.status}`);
}, version);

const notice = (page) => page.getByRole("region", { name: "What's new" });

test("Scenario: the first open after installing shows no update notice", async () => {
  const { page } = await h.newDevice(browser);
  await h.signIn(page, server.url, "u20@example.com");
  await page.reload();
  await page.getByRole("textbox", { name: "Tell me anything" }).waitFor();
  await page.waitForTimeout(500);
  assert.equal(await notice(page).count(), 0);
});

test("Scenario: the app says what changed after an update", async () => {
  const { page } = await h.newDevice(browser);
  await h.signIn(page, server.url, "u21@example.com");
  await setSeen(page, "0.1.0");
  await page.reload();
  await notice(page).waitFor();
  const text = await notice(page).innerText();
  assert.match(text, /Updated to 0\.2\.0/);
  assert.match(text, /Second test change/);
  assert.doesNotMatch(text, /First test change|Third test change/);
  await notice(page).getByRole("button", { name: "Got it" }).click();
  await h.count(notice(page), 0);
  await page.reload();
  await page.getByRole("textbox", { name: "Tell me anything" }).waitFor();
  await page.waitForTimeout(500);
  assert.equal(await notice(page).count(), 0);
});

test("Scenario: an open app offers a new version when one is deployed", async () => {
  const { page } = await h.newDevice(browser);
  await h.signIn(page, server.url, "u22@example.com");
  await deploy(page, "0.3.0");
  try {
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));   // back to the front
    const update = page.getByRole("button", { name: "Update now" });
    await update.waitFor({ timeout: 5000 });
    await page.getByText("A new version of Dumpit is ready").waitFor();
    await deploy(page, "0.2.0");          // the reload fetches what the server now serves
    await Promise.all([page.waitForEvent("load"), update.click()]);
    await page.getByRole("textbox", { name: "Tell me anything" }).waitFor();
    assert.equal(await page.getByRole("button", { name: "Update now" }).count(), 0);
  } finally {
    await deploy(page, "0.2.0");
  }
});

test("Scenario: the app shows which version it is", async () => {
  const { page } = await h.newDevice(browser);
  await h.signIn(page, server.url, "u23@example.com");
  await page.getByRole("button", { name: "Devices and sign-out" }).click();
  await page.getByText("Dumpit 0.2.0").waitFor();
});
