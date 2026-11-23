import { afterEach, describe, expect, it, vi } from "vitest";

import {
  forgetActiveJob,
  readActiveJobId,
  readJobIdFromUrl,
  rememberActiveJob,
  writeJobIdToUrl,
} from "@/lib/job-deep-link";

// No jsdom here: a minimal `window` whose history.replaceState updates location.
function stubWindow(href: string) {
  const store = new Map<string, string>();
  const win = {
    location: { href },
    sessionStorage: {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
    },
    history: {
      replaceState: (_s: unknown, _t: string, path: string) => {
        win.location.href = new URL(path, win.location.href).href;
      },
    },
  };
  vi.stubGlobal("window", win);
  return win;
}

describe("job deep link", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("round-trips the active job id through the URL", () => {
    const win = stubWindow("http://localhost:3000/generate?x=1");
    expect(readJobIdFromUrl()).toBeUndefined();
    writeJobIdToUrl("job-abc123");
    expect(win.location.href).toBe("http://localhost:3000/generate?x=1&job=job-abc123");
    expect(readJobIdFromUrl()).toBe("job-abc123");
  });

  it("is a no-op without a window (server render)", () => {
    expect(readJobIdFromUrl()).toBeUndefined();
    expect(() => writeJobIdToUrl("job-x")).not.toThrow();
  });

  it("falls back to this tab's stored job when navigation dropped the query", () => {
    stubWindow("http://localhost:3000/generate");
    expect(readActiveJobId()).toBeUndefined();
    rememberActiveJob("job-1");
    expect(readActiveJobId()).toBe("job-1");
    writeJobIdToUrl("job-2");
    expect(readActiveJobId()).toBe("job-2"); // the URL wins
  });

  it("forgets only the finished job, never a newer one", () => {
    stubWindow("http://localhost:3000/generate");
    rememberActiveJob("job-new");
    forgetActiveJob("job-old");
    expect(readActiveJobId()).toBe("job-new");
    forgetActiveJob("job-new");
    expect(readActiveJobId()).toBeUndefined();
  });
});
