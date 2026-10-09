import { score } from "./internal/score";

test("score doubles", () => {
  expect(score(2)).toBe(4);
});
