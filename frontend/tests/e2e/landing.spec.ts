import { expect, test } from "@playwright/test";

test.describe("Landing page", () => {
  test("root shows the Changban consulting page", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", { level: 1, name: /都有长伴相随/ }),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "wangjian@cbrlzy.com" })).toBeVisible();
  });
});
