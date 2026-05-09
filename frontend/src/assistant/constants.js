/** Chip labels + full queries (factual phrasing; avoid advisory triggers) */

export const PROMPT_CHIPS = [
  { label: 'Exit load', query: 'What is the exit load for HDFC Mid Cap Fund?' },
  { label: 'SIP minimum', query: 'What is the minimum SIP for HDFC ELSS Tax Saver Fund?' },
  { label: 'ELSS lock-in', query: 'What is the lock-in period for HDFC ELSS Tax Saver Fund?' },
  { label: 'Expense ratio', query: 'What is the expense ratio of HDFC Flexi Cap Fund?' },
  { label: 'Benchmark', query: 'What is the benchmark index for HDFC Nifty 50 Index Fund?' },
]

export const ROTATING_PLACEHOLDERS = [
  'Ask about exit load…',
  'Expense ratio for HDFC Mid Cap…',
  'Lock-in for ELSS…',
  'Housing Opportunities Fund…',
  'Minimum SIP for Balanced Advantage…',
]

export const TRUST_TOOLTIP =
  'This assistant answers only from a fixed HDFC Mutual Fund corpus and may not reflect live market updates. It does not provide investment advice.'
