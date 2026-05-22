// Regression gate: no source file under web/src/ (excluding tests) may contain
// the literal "http://localhost:8000". All API base fallbacks must use "" so that
// same-origin proxy (Phase 14-A) works on non-localhost devices.

import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const SRC_ROOT = join(__dirname, "../../");
const LITERAL = "http://localhost:8000";

function collectSourceFiles(dir: string): string[] {
  const results: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (entry === "tests" || entry === "__tests__" || entry === "node_modules") continue;
      results.push(...collectSourceFiles(full));
    } else if (/\.(ts|tsx)$/.test(entry) && !/\.(test|spec)\.(ts|tsx)$/.test(entry)) {
      results.push(full);
    }
  }
  return results;
}

describe("no hardcoded API base (P14-A regression)", () => {
  it(`no .ts/.tsx source file contains "${LITERAL}"`, () => {
    const files = collectSourceFiles(SRC_ROOT);
    const violations = files.filter((f) => readFileSync(f, "utf-8").includes(LITERAL));
    expect(
      violations,
      `Found "${LITERAL}" in:\n${violations.map((f) => "  " + relative(SRC_ROOT, f)).join("\n")}`,
    ).toHaveLength(0);
  });
});
