import { total } from "../src/billing";

test("total adds amounts", () => {
  expect(total([1, 2])).toBe(3);
});
