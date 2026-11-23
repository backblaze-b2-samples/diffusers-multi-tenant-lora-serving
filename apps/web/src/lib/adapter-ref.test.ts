import { describe, expect, it } from "vitest";

import {
  formatAdapterRef,
  isCrossTenant,
  isolationMessage,
  parseAdapterRef,
} from "@/lib/adapter-ref";

describe("parseAdapterRef", () => {
  it("parses the three accepted shapes", () => {
    expect(parseAdapterRef("pixel-art")).toEqual({ owner: null, name: "pixel-art", version: null });
    expect(parseAdapterRef("pixel-art@v2")).toEqual({ owner: null, name: "pixel-art", version: "v2" });
    expect(parseAdapterRef("globex/papercut@v1.0")).toEqual({
      owner: "globex",
      name: "papercut",
      version: "v1.0",
    });
  });

  it.each(["", "a", "../x", "a/b/c", "pixel-art@latest", "Pixel", "x@v1@v2"])(
    "rejects %s",
    (ref) => expect(parseAdapterRef(ref)).toBeNull(),
  );

  it("flags another tenant as owner", () => {
    expect(isCrossTenant(parseAdapterRef("globex/papercut")!, "acme")).toBe(true);
    expect(isCrossTenant(parseAdapterRef("acme/pixel-art")!, "acme")).toBe(false);
    expect(isCrossTenant(parseAdapterRef("pixel-art")!, "acme")).toBe(false);
  });

  it("formats form selections", () => {
    expect(formatAdapterRef("pixel-art", "v1")).toBe("pixel-art@v1");
    expect(formatAdapterRef("pixel-art")).toBe("pixel-art");
  });

  it("explains isolation codes", () => {
    expect(isolationMessage("cross_tenant_adapter")).toMatch(/403/);
    expect(isolationMessage("adapter_not_found")).toMatch(/404/);
    expect(isolationMessage("something_else")).toBeNull();
  });
});
