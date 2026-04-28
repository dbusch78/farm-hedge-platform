# Farm Platform -- Claude Code Instructions

Read CLAUDE_CODE_BRIEF.md for full architecture and context.
Read SESSION_NOTES.md for where we left off.
Read the milestone checklist and find the first unchecked item.
Start there. Do not re-do completed work.
When you finish a task, check it off and commit.
When you end a session, update SESSION_NOTES.md with what was done 
and what comes next.

---

## Unit Handling Rules (read before touching any price or feed code)

### CBOT grain futures: ALWAYS dollars per bushel internally

CBOT grain futures (ZC, ZS, ZW) are quoted by exchanges and many data
providers in **cents** per bushel. Inside this codebase, all prices MUST
be stored, computed, and displayed in **dollars** per bushel.

Sanity-check ranges (if a value is outside these, it is almost certainly
in cents and the conversion at the feed boundary is missing or broken):

| Symbol | Typical range ($/bu) |
|--------|----------------------|
| ZC     | $3.00 – $8.00        |
| ZS     | $8.00 – $18.00       |
| ZW     | $4.00 – $12.00       |
| Strikes & premiums follow the same underlying ranges |

### Conversion happens at the data feed boundary, nowhere else

The ONLY place unit conversion should happen is inside the data feed
module that ingests external prices (`farm_platform/feeds/`). Calculators,
storage, and display all assume dollars-per-bushel.

If you find yourself dividing or multiplying by 100 outside a feed module,
stop — you are patching a symptom, not fixing the root cause.

### Required: assertion tests on every price-ingesting feed

Every feed function that returns a futures price MUST have a test that
asserts the stored value is in the dollar range:

```python
def test_<provider>_<symbol>_returns_dollars():
    price = ...  # call or inspect the feed output
    assert 1.0 < price < 50.0, (
        f"Price {price} for <symbol> looks like cents, not dollars. "
        "Conversion at ingestion boundary may be missing or broken."
    )
```

This test must exist for every (provider, symbol) pair in production. If
you add a new data source or contract, add the test in the same PR.

### Options premiums: same rule

Option premiums on grain options are also quoted in cents by the exchange.
Store and compute in dollars-per-bushel. A typical ATM corn call: ~$0.20.
A deep ITM bean call: ~$1.50. Premiums above $5.00 for corn or $10.00 for
beans are red flags.

### Bushel quantities: never confuse with prices

Contract size for ZC and ZS is 5,000 bushels.

    total_$ = price_per_bushel × bushels_held   (bushels_held = contracts × 5000)

Do NOT multiply a price by 5,000 unless explicitly converting per-bushel
to per-contract, and name the variable accordingly (`premium_per_contract`,
not `premium`).

### History

This rule exists because of a real bug: `futures_feed.py` stored yfinance
quotes in native cents, which propagated into the calculator, Black-76
delta, and display. P&L showed as $468/bu instead of $0.08/bu. Fixed in
commit 625fc07. The bug survived because no test asserted unit correctness
at the ingestion boundary.

---

## Aggregation Across Multiple Positions

When rolling up data across multiple positions of the same commodity or contract,
use **group-by-and-aggregate** — never `.find()` or first-match. First-match
silently drops additional positions and produces results that look correct on
small data (one position per commodity) but break the moment a user has more
than one position per commodity.

### Required pattern: explicit aggregation with exposure-weighted averages

For per-bushel metrics (P&L/bu, net effective price, premiums paid/bu):
weight by **bushels held** (or equivalently `raw_contracts = expected_bushels / 5000`).

For total-dollar/count metrics (`delta_adj_contracts`, `raw_contracts`): sum.

```python
total_raw = sum(r["raw_contracts"] for r in group)
wavg_pnl = sum(r["options_pnl_per_bu"] * r["raw_contracts"] for r in group) / total_raw
```

### Why contract-count weighting matters

A 3-contract position should carry 3× the weight of a 1-contract position when
computing blended per-bushel P&L. Equal weights (simple average) are wrong in
the same way as weighting portfolio P&L by number of positions instead of
dollar exposure.

### Aggregation bugs hide behind similar inputs

This bug was invisible on the corn card because both corn legs had similar P&L
(~+$0.07/bu each). It revealed itself on beans because one leg was deep ITM
(+$1.22/bu) and the other barely ITM (-$0.23/bu). Design regression tests with
deliberately divergent inputs so that dropping any position produces a noticeably
wrong aggregate.

### History

Fixed in commit 39651f5 (Issue #8). The backend `/net-price` endpoint appended
one row per position; the frontend's `.find()` picked only the first ZS match,
showing -$0.20/bu instead of the correct blended +$0.88/bu across two bean positions.

---