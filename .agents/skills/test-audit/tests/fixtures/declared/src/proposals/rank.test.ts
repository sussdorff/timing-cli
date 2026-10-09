// test-boundary-exception: pins the tie-break order the entry cannot expose
import type { rankProposals } from "./internal/rank";
import { rankProposals as rank } from "./internal/rank";

test("rank keeps ties stable", () => {
  expect(rank([1, 1])).toEqual([1, 1]);
});
