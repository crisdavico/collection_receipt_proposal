/** @odoo-module **/

/* Reads the amounts an operator types on the board, and writes the seeds those
   inputs start from. The inputs are free text with `inputmode="decimal"`, so
   an es_AR board receives `500,50` from one operator and `500.50` from another
   on a numpad or with an en_US habit -- and the old parser, which dropped every
   `.`, read the second one as 50050.

   This module has NO imports on purpose: the caller passes the user's
   separators (Odoo's `localization.decimalPoint` / `localization.thousandsSep`)
   and plain Node can load the file, which is how
   `tests/amount_parser_test.js` checks it.

   The rules, for one decimal point D and one thousands separator T:
   - a thousands separator is accepted only in valid groups: 1 to 3 digits,
     then groups of exactly 3;
   - with both `.` and `,` present, the last one is the decimal point;
   - with a single kind of separator, it is the decimal point when it appears
     once and its last group is not exactly 3 digits (`500.50`);
   - a single separator before exactly 3 digits is the decimal point if it is
     D and a thousands separator if it is T (`1.234` is 1234 in es_AR and
     1.234 in en_US); any other mark there is ambiguous;
   - anything ambiguous or malformed is NaN, never a silently wrong number. */

const DOT = ".";
const COMMA = ",";
const DIGIT = /^[0-9]$/u;

function readSeparators(separators) {
  const given = separators || {};
  return {
    decimalPoint: given.decimalPoint || DOT,
    thousandsSep: given.thousandsSep || "",
  };
}

/* Digit groups and the marks between them, or null on any other character. */
function tokenize(body, marks) {
  const groups = [""];
  const seps = [];
  for (const char of body) {
    if (DIGIT.test(char)) {
      groups[groups.length - 1] += char;
    } else if (marks.has(char)) {
      seps.push(char);
      groups.push("");
    } else {
      return null;
    }
  }
  return {groups, seps};
}

/* Whether the last mark is the decimal point: true, false, or null when the
   text cannot tell. */
function lastMarkIsDecimal(groups, seps, decimalPoint, thousandsSep) {
  if (!seps.length) {
    return false;
  }
  const last = seps[seps.length - 1];
  if (last !== DOT && last !== COMMA && last !== decimalPoint) {
    return false;
  }
  if (new Set(seps).size > 1) {
    return seps.filter((sep) => sep === last).length === 1 ? true : null;
  }
  if (seps.length > 1) {
    return false;
  }
  if (groups[groups.length - 1].length !== 3 || last === decimalPoint) {
    return true;
  }
  return last === thousandsSep ? false : null;
}

/* The integer part's digits, or null when its grouping is not 1-3 then 3s. */
function integerDigits(groups, seps) {
  if (!seps.length) {
    return groups[0];
  }
  if (new Set(seps).size > 1) {
    return null;
  }
  const [head, ...tail] = groups;
  const valid =
    head.length >= 1 && head.length <= 3 && tail.every((group) => group.length === 3);
  return valid ? groups.join("") : null;
}

/* The typed text, trimmed, with any whitespace read as the thousands separator
   when the locale groups with a space: a plain space typed
   for a narrow no-break one still reads as a group mark. */
function normalizeText(raw, thousandsSep) {
  const text = String(raw === undefined || raw === null ? "" : raw).trim();
  return /^\s$/u.test(thousandsSep) ? text.replace(/\s/gu, thousandsSep) : text;
}

/* The unsigned amount written in `body`, or NaN. */
function parseUnsigned(body, decimalPoint, thousandsSep) {
  const marks = new Set([DOT, COMMA, decimalPoint, thousandsSep].filter(Boolean));
  const tokens = tokenize(body, marks);
  if (!tokens) {
    return NaN;
  }
  const {groups, seps} = tokens;
  const decimal = lastMarkIsDecimal(groups, seps, decimalPoint, thousandsSep);
  if (decimal === null) {
    return NaN;
  }
  const integer = decimal
    ? integerDigits(groups.slice(0, -1), seps.slice(0, -1))
    : integerDigits(groups, seps);
  const fraction = decimal ? groups[groups.length - 1] : "";
  if (integer === null || (!integer && !fraction)) {
    return NaN;
  }
  return Number(`${integer || "0"}.${fraction || "0"}`);
}

export function parseAmount(raw, separators) {
  if (typeof raw === "number") {
    return Number.isFinite(raw) ? raw : NaN;
  }
  const {decimalPoint, thousandsSep} = readSeparators(separators);
  const text = normalizeText(raw, thousandsSep);
  if (text.startsWith("-")) {
    return -parseUnsigned(text.slice(1), decimalPoint, thousandsSep);
  }
  return parseUnsigned(text, decimalPoint, thousandsSep);
}

/* The seed of an amount input: the user's decimal point and no thousands
   separator, so `parseAmount` reads it back as the same number in every
   locale -- `1000,5` on es_AR, `1000.5` on en_US. */
export function rawAmount(value, separators) {
  const amount = Number(value);
  const {decimalPoint} = readSeparators(separators);
  return String(Number.isFinite(amount) ? amount : 0).replace(DOT, decimalPoint);
}
