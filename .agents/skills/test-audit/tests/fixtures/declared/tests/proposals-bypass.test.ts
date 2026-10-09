import { mock } from "bun:test";

mock.module("../src/proposals/internal/score", () => ({ score: () => 0 }));

test("ranks with a mocked score", async () => {
  const { rankProposals } = await import("../src/proposals");
  expect(rankProposals([1, 3])).toEqual([1, 3]);
});
