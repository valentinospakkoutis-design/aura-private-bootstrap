// Reject the entire quote rather than mixing values from different messages.
export function normalizeQuote(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
  const { price, bid, ask } = data;
  if (![price, bid, ask].every(v => typeof v === 'number' && Number.isFinite(v) && v > 0)) return null;
  if (bid > ask) return null;
  return { price, bid, ask,
    priceAsof: [data.priceAsof, data.market_asof, data.asof, data.fetched_at]
      .find(v => typeof v === 'string' && Number.isFinite(Date.parse(v))) ?? null,
    stale: data.stale === true };
}

export function applyQuote(state, data, { updatePriceUI, processTick, renderPositions }, isReal = true) {
  const quote = normalizeQuote(data);
  if (!quote) return false;
  if (quote.priceAsof && state.priceAsof &&
      Date.parse(quote.priceAsof) < Date.parse(state.priceAsof)) return false;
  Object.assign(state, quote);
  if (state.anchor === null) state.anchor = quote.price;
  updatePriceUI();
  processTick(quote.price, isReal);
  renderPositions();
  return true;
}
