// Starts tests/e2e_server.py (throwaway Postgres + demo filer + the built web app) and signs
// browsers in through the dev sign-in link. Uses the Playwright that is installed globally.
const { spawn } = require("node:child_process");
const path = require("node:path");
const { chromium, devices } = require("playwright");

const ROOT = path.resolve(__dirname, "..", "..");

function startServer() {
  return new Promise((resolve, reject) => {
    const proc = spawn("python3", ["-m", "tests.e2e_server"], { cwd: ROOT, stdio: ["ignore", "pipe", "inherit"],
      env: { ...process.env, APP_VERSION: process.env.APP_VERSION || "0.2.0", DUMPIT_CHANGELOG: path.join(ROOT, "tests", "fixtures", "changelog.md") } });
    let out = "";
    const timer = setTimeout(() => reject(new Error("server did not start in 60 s")), 60000);
    proc.stdout.on("data", (chunk) => {
      out += chunk;
      const m = out.match(/READY (\S+)/);
      if (m) { clearTimeout(timer); resolve({ url: m[1], stop: () => new Promise((r) => { proc.once("exit", r); proc.kill("SIGTERM"); }) }); }
    });
    proc.once("exit", (code) => { clearTimeout(timer); reject(new Error(`server exited (${code})`)); });
  });
}

async function launch() {
  return chromium.launch(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {});
}

async function newDevice(browser, kind = "phone") {
  const context = await browser.newContext(kind === "phone" ? { ...devices["iPhone 13"] } : { viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();
  return { context, page };
}

async function signIn(page, url, email) {
  await page.goto(url);
  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: /sign-in link|Send a new link/ }).click();
  await page.getByRole("button", { name: "Dev: open the sign-in link" }).click();
  await page.getByRole("textbox", { name: "Tell me anything" }).waitFor();
}

async function send(page, text) {
  const box = page.getByRole("textbox", { name: "Tell me anything" });
  await box.fill(text);
  await box.press("Enter");
}

/** The signed-in user's own data, as the server has it. */
async function changes(page) {
  return page.evaluate(async () => (await fetch("/v1/changes")).json());
}

async function seed(page, body) {
  const res = await page.evaluate(async (b) => (await fetch("/__seed", { method: "POST", body: JSON.stringify(b),
    headers: { "Content-Type": "application/json" } })).status, body);
  if (res !== 200) throw new Error(`seed failed: ${res}`);
}

async function today(page) {
  return page.evaluate(() => { const d = new Date(), p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`; });
}

/** Wait until a locator matches exactly n elements (pages settle asynchronously). */
async function count(locator, n, timeout = 5000) {
  const until = Date.now() + timeout;
  let last;
  while (Date.now() < until) {
    last = await locator.count();
    if (last === n) return;
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error(`expected ${n} matches, found ${last}`);
}

module.exports = { count, startServer, launch, newDevice, signIn, send, changes, seed, today };
