# Code Review — Original Nassau Candy Notebook

## Overall assessment
The notebook is a solid exploratory starting point: it profiles basic data quality, calculates product and division gross margin, ranks products, performs a Pareto-style concentration analysis, and plots monthly margin. It is not yet publication-ready or deployment-ready because several calculations depend on mutable notebook state, some code is duplicated, a column-name mismatch can break a chart, and the date fields need source validation.

## Findings

### High priority
1. **Ship-date anomaly.** All 10,194 ship dates occur after order dates, but the lag is 904–1,642 days (median 1,274). The notebook currently does not surface this issue. Validate source date parsing, synthetic date generation, or data transformation before making any shipping-performance claims.
2. **Mutable `avg_margin` variable.** Cell 15 sets `avg_margin` to the mean product margin. Cell 20 later overwrites it with the mean division margin. Because Jupyter cells can be run out of order, re-running cell 16 after cell 20 can change the definition of `high_sales_low_margin`. Use distinct names such as `mean_product_margin` and `mean_division_margin`, or preferably a business-defined threshold.
3. **Profit-contribution column mismatch.** Cell 54 creates `Profit Contribution(%)`, while cell 55 refers to `Profit Contribution (%)`. The mismatch can raise a `KeyError`. Standardize one exact column name.
4. **Unweighted mean margin is not the company margin.** The mean of product margins or division margins treats tiny and large products/divisions equally. Company-level gross margin should be `sum(Gross Profit) / sum(Sales) * 100`. Division margins should be weighted within each division using summed profit divided by summed sales.
5. **Discontinuation logic is too simplistic.** Cell 41 flags low-sales/low-profit products. That is a screening rule, not proof a product should be discontinued. Review demand, customer/strategic importance, seasonality, contribution, substitution, inventory, and costs first.

### Medium priority
6. **Aggregation key.** Product summary starts with `Product Name` only. Group by both `Product ID` and `Product Name` so different SKUs are not merged if names collide.
7. **Date conversion is repeated.** Order Date is parsed in multiple cells with a fixed format. Parse once using `pd.to_datetime(..., dayfirst=True, errors='coerce')`, report parse failures, and reuse the parsed column.
8. **Cost reconciliation should be explicit.** Check `abs(Sales - Cost - Gross Profit) <= tolerance` and report mismatches rather than assuming profit is valid because it is nonnegative.
9. **Revenue and profit Pareto labels.** The current “count under 80% + 1” works for the crossing point in common cases but should be tested when cumulative share lands exactly on 80%, when there are zero/negative contributions, or when no products exist.
10. **Duplicated work.** Cost summaries, division summaries, product summaries, and monthly charts are recreated in later cells. Build reusable summary functions and one canonical set of names.
11. **Static conclusions.** Markdown conclusions such as “no structural margin issues” are not generated from current results and can become stale when data changes. Generate interpretations from current outputs or label them as a dated finding.
12. **Visualization readability.** Product charts have long labels; horizontal bars or interactive Plotly charts improve readability. Add number formatting, units, and explicit date windows.
13. **No reusable application interface.** The notebook assumes a fixed Kaggle input path. For local/Streamlit use, allow a file uploader or configurable relative path.

## Results reproduced from the supplied CSV
- Rows/columns: 10,194 × 18.
- Sales: $141,783.63.
- Gross profit: $93,442.80.
- Cost: $48,340.83.
- Units: 38,654.
- Weighted gross margin: 65.91%.
- Reconciliation: no rows differ from `Sales - Cost - Gross Profit` by more than $0.011.
- Missing cells: none; duplicate full rows: none.
- Chocolate: $131,692.90 sales, $88,824.62 gross profit, 67.45% margin, 92.88% of sales.
- Other: $9,663.25 sales, $4,333.45 gross profit, 44.84% margin, 6.82% of sales.
- Sugar: $427.48 sales, $284.73 gross profit, 66.61% margin, 0.30% of sales.
- Kazookles: $1,205.75 sales, $92.75 gross profit, 7.69% margin; highest-priority margin review candidate by the supplied figures.
- Wonka Bar -Scrumdiddlyumptious has the largest product gross profit ($19,357.50); Triple Dazzle Caramel has the highest sales ($28,485.00).
- The top five Chocolate products together account for most sales; revenue concentration should be monitored.
- Order dates run 2024-01-02 to 2025-12-31; 4,181 rows in 2024 and 6,013 in 2025.

## Recommended refactor
- Put loading/validation in one function.
- Parse dates once; preserve raw fields if auditability matters.
- Use explicit names such as `product_summary`, `division_summary`, `monthly_summary`, `mean_product_margin`.
- Use a weighted formula for overall margin.
- Separate flags (screening criteria) from decisions (management action).
- Add assertions/tests for required columns, nonnegative amounts, reconciliation, and date anomalies.
- Export summaries and log validation results.
- Build the dashboard with user-selectable filters and data upload instead of hard-coded paths.
