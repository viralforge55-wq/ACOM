import type { Money } from "@/types/catalog";

const CURRENCY_SYMBOLS: Record<string, string> = {
  INR: "₹",
  USD: "$",
  EUR: "€",
  GBP: "£",
};

/**
 * Format a server-supplied decimal string without converting to float.
 * Groups integer digits using Indian numbering for INR and standard 3-digit grouping otherwise.
 */
export function formatMoney(money: Money): string {
  const raw = (money.amount || "").trim();
  const match = /^(-?)(\d+)(?:\.(\d{1,2}))?$/.exec(raw);
  if (!match) {
    return `${money.currency} ${raw}`;
  }

  const [, sign, intPart, fracPart = "00"] = match;
  const paddedFrac = fracPart.padEnd(2, "0");
  const code = (money.currency || "INR").toUpperCase();
  const symbol = CURRENCY_SYMBOLS[code] ?? `${code} `;

  const grouped = code === "INR" ? groupIndian(intPart) : groupStandard(intPart);
  return `${sign}${symbol}${grouped}.${paddedFrac}`;
}

function groupIndian(digits: string): string {
  if (digits.length <= 3) return digits;
  const lastThree = digits.slice(-3);
  const rest = digits.slice(0, -3);
  const groupedRest = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  return `${groupedRest},${lastThree}`;
}

function groupStandard(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}
