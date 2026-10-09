import { score } from "./score";

export function rankProposals(values: number[]): number[] {
  return [...values].sort((a, b) => score(b) - score(a));
}
