import {
  rankProposals,
} from "../src/proposals";
import { something } from "dep";

test("ranks higher first", () => {
  expect(rankProposals([1, 3])).toEqual([3, 1]);
});
