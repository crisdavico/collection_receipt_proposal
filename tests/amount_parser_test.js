/* eslint-env node */

/* Plain-Node checks for the board's amount parser.

   `amount_parser.esm.js` has no imports, so it loads outside Odoo: the file is
   read and imported as a data URL, which sidesteps Node's CommonJS default for
   `.js`. `test_receipt_proposal_amount_parser.py` runs this script inside the
   Odoo suite; it also runs on its own with `node tests/amount_parser_test.js`.
   Exit code 0 and a "checks passed" line mean every case matched. */

const fs = require("node:fs");
const path = require("node:path");

const PARSER = path.join(
  __dirname,
  "..",
  "static",
  "src",
  "receipt_proposal",
  "amount_parser.esm.js"
);

const ES_AR = {decimalPoint: ",", thousandsSep: "."};
const EN_US = {decimalPoint: ".", thousandsSep: ","};
const FR_FR = {decimalPoint: ",", thousandsSep: " "};

/* [separators, typed text, expected number]. NaN means "refuse": an
   ambiguous or malformed amount never becomes a silently wrong number. */
const PARSE_CASES = [
  [ES_AR, "500,50", 500.5],
  [ES_AR, "500.50", 500.5],
  [ES_AR, "1.234", 1234],
  [ES_AR, "1.234,56", 1234.56],
  [ES_AR, "1.234.567", 1234567],
  [ES_AR, "1.234.567,8", 1234567.8],
  [ES_AR, "12.34.5", NaN],
  [ES_AR, "1.234.56", NaN],
  [ES_AR, "1234.567", NaN],
  [ES_AR, "1,234", 1.234],
  [ES_AR, "1,234,567", 1234567],
  [ES_AR, "1,2,3", NaN],
  [ES_AR, "1.234,567,8", NaN],
  [ES_AR, "1..5", NaN],
  [ES_AR, ".234", NaN],
  [ES_AR, "0,5", 0.5],
  [ES_AR, ",5", 0.5],
  [ES_AR, "500,", 500],
  [ES_AR, "500", 500],
  [ES_AR, "  500,50  ", 500.5],
  [ES_AR, "-500,50", -500.5],
  [ES_AR, "", NaN],
  [ES_AR, "   ", NaN],
  [ES_AR, ",", NaN],
  [ES_AR, "-", NaN],
  [ES_AR, "abc", NaN],
  [ES_AR, "1e3", NaN],
  [ES_AR, "12a", NaN],
  [ES_AR, "$ 500", NaN],
  [ES_AR, null, NaN],
  [ES_AR, undefined, NaN],
  [ES_AR, 1000.5, 1000.5],
  [ES_AR, Infinity, NaN],
  [EN_US, "500.50", 500.5],
  [EN_US, "500,50", 500.5],
  [EN_US, "1,234", 1234],
  [EN_US, "1,234.56", 1234.56],
  [EN_US, "1,234,567", 1234567],
  [EN_US, "1.234", 1.234],
  [EN_US, "1.234,56", 1234.56],
  [EN_US, "1234,567", NaN],
  [EN_US, "12,34,5", NaN],
  [EN_US, ".5", 0.5],
  [FR_FR, "1 234,56", 1234.56],
  [FR_FR, "1 234,56", 1234.56],
  [FR_FR, "1 234", 1234],
  [FR_FR, "1.234", NaN],
  [FR_FR, "1.5", 1.5],
  [FR_FR, "12 34", NaN],
];

/* `rawAmount` seeds an input that is read back with `parseAmount`, so every
   seed has to survive the round trip in the locale that typed it. */
const RAW_CASES = [
  [ES_AR, 1000.5, "1000,5"],
  [ES_AR, 1234, "1234"],
  [ES_AR, 1.234, "1,234"],
  [ES_AR, 0, "0"],
  [ES_AR, "x", "0"],
  [EN_US, 1000.5, "1000.5"],
  [EN_US, 1.234, "1.234"],
  [FR_FR, 1234.56, "1234,56"],
];

function describe(value) {
  "use strict";
  return typeof value === "string" ? JSON.stringify(value) : String(value);
}

async function main() {
  "use strict";
  const source = await fs.promises.readFile(PARSER, "utf8");
  const url = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
  const {parseAmount, rawAmount} = await import(url);
  const failures = [];
  for (const [separators, input, expected] of PARSE_CASES) {
    const actual = parseAmount(input, separators);
    if (!Object.is(actual, expected)) {
      failures.push(
        `parseAmount(${describe(input)}, ${JSON.stringify(separators)}) = ` +
          `${describe(actual)}, expected ${describe(expected)}`
      );
    }
  }
  for (const [separators, value, expected] of RAW_CASES) {
    const seed = rawAmount(value, separators);
    if (seed !== expected) {
      failures.push(
        `rawAmount(${describe(value)}, ${JSON.stringify(separators)}) = ` +
          `${describe(seed)}, expected ${describe(expected)}`
      );
    }
    const amount = Number(value);
    const back = parseAmount(seed, separators);
    if (Number.isFinite(amount) && !Object.is(back, amount)) {
      failures.push(
        `round trip of ${describe(value)} in ${JSON.stringify(separators)} ` +
          `read back ${describe(back)}`
      );
    }
  }
  const checks = PARSE_CASES.length + RAW_CASES.length * 2;
  if (failures.length) {
    console.error(failures.join("\n"));
    console.error(`amount_parser: ${failures.length} of ${checks} checks failed`);
    process.exitCode = 1;
    return;
  }
  console.log(`amount_parser: ${checks} checks passed`);
}

main();
