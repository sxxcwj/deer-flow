import { describe, expect, it } from "vitest";

import { avatarKind } from "@/core/agents/avatar";

describe("avatarKind", () => {
  it("treats blank values as empty", () => {
    expect(avatarKind(null)).toBe("empty");
    expect(avatarKind("  ")).toBe("empty");
  });

  it("treats http(s) urls as images", () => {
    expect(avatarKind("https://example.com/a.png")).toBe("image");
  });

  it("treats emoji as text", () => {
    expect(avatarKind("🦌")).toBe("text");
  });
});
