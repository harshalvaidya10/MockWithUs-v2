import { expect, test } from "@playwright/test";

type ResumeRow = {
  id: string;
  filename: string;
  skills: string[];
  created_at: string;
  is_resume_like: boolean;
};

test("delete resume removes row and stays deleted after refresh", async ({ context, page }) => {
  const cookieUrl = test.info().project.use.baseURL ?? "http://127.0.0.1:3100";
  await context.addCookies([
    {
      name: "mockwithus_access_token",
      value: "e2e-access-token",
      url: cookieUrl,
    },
  ]);

  const resumes: ResumeRow[] = [
    {
      id: "11111111-1111-1111-1111-111111111111",
      filename: "resume-keep.pdf",
      skills: ["Python", "FastAPI"],
      created_at: "2026-04-08T06:35:09.913153Z",
      is_resume_like: true,
    },
    {
      id: "22222222-2222-2222-2222-222222222222",
      filename: "resume-delete.pdf",
      skills: ["TypeScript"],
      created_at: "2026-04-08T06:40:09.913153Z",
      is_resume_like: true,
    },
  ];

  await page.route("http://mock-api.local/auth/me", async (route) => {
    if (route.request().method() !== "GET") {
      await route.fulfill({ status: 405 });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        email: "e2e@example.com",
        full_name: "E2E User",
        created_at: "2026-04-08T06:00:00.000000Z",
      }),
    });
  });

  await page.route("http://mock-api.local/resumes/**", async (route) => {
    const request = route.request();
    const requestUrl = new URL(request.url());
    const method = request.method();

    if (method === "GET" && (requestUrl.pathname === "/resumes/" || requestUrl.pathname === "/resumes")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(resumes),
      });
      return;
    }

    if (method === "DELETE" && requestUrl.pathname.startsWith("/resumes/")) {
      const resumeId = requestUrl.pathname.split("/").at(-1);
      if (!resumeId) {
        await route.fulfill({ status: 400, contentType: "application/json", body: "{\"detail\":\"Invalid resume id.\"}" });
        return;
      }

      const index = resumes.findIndex((resume) => resume.id === resumeId);
      if (index === -1) {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: "{\"detail\":\"Resume not found.\"}",
        });
        return;
      }

      resumes.splice(index, 1);
      await route.fulfill({ status: 204, body: "" });
      return;
    }

    await route.fulfill({
      status: 405,
      contentType: "application/json",
      body: "{\"detail\":\"Unsupported mocked request.\"}",
    });
  });

  await page.goto("/resumes");

  await expect(page.locator("li", { hasText: "resume-delete.pdf" })).toHaveCount(1);
  await expect(page.locator("li", { hasText: "resume-keep.pdf" })).toHaveCount(1);

  page.once("dialog", async (dialog) => {
    await dialog.accept();
  });
  await page.locator("li", { hasText: "resume-delete.pdf" }).getByRole("button", { name: "Delete" }).click();

  await expect(page.locator("li", { hasText: "resume-delete.pdf" })).toHaveCount(0);
  await expect(page.locator("li", { hasText: "resume-keep.pdf" })).toHaveCount(1);

  await page.reload();

  await expect(page.locator("li", { hasText: "resume-delete.pdf" })).toHaveCount(0);
  await expect(page.locator("li", { hasText: "resume-keep.pdf" })).toHaveCount(1);
});
