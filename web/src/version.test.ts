import { describe, expect, it } from "vitest";
import { afterOpen, offerReload, shown } from "./version";

describe("version notice decisions (slice 15)", () => {
  it("the first open after installing shows no update notice", () => {
    expect(afterOpen(undefined, "0.2.0")).toBe("first-run");
    expect(afterOpen(null, "0.2.0")).toBe("first-run");
  });
  it("the app says what changed after an update", () => {
    expect(afterOpen("0.1.0", "0.2.0")).toBe("updated");
    expect(afterOpen("0.2.0", "0.2.0")).toBe("none");
  });
  it("an open app offers a new version when one is deployed", () => {
    expect(offerReload("0.3.0", "0.2.0")).toBe(true);
    expect(offerReload("0.2.0", "0.2.0")).toBe(false);
    expect(offerReload(undefined, "0.2.0")).toBe(false);   // offline or unknown: say nothing
    expect(offerReload("0.1.0", "0.2.0")).toBe(true);      // rolled back: match the server
  });
  it("shows versions without the tag's v", () => {
    expect(shown("v1.2.0")).toBe("1.2.0");
    expect(shown("dev")).toBe("dev");
  });
});
