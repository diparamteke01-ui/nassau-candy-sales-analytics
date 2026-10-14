# Nassau Candy Distributor — Profitability Dashboard

## Run in VS Code on Windows
1. Keep `app.py`, `requirements.txt`, and `Nassau Candy Distributor.csv` in the same folder.
2. Open the folder in VS Code and choose **Terminal → New Terminal**.
3. Run `python -m venv .venv`
4. Activate it: `.venv\Scripts\activate`
5. Install packages: `python -m pip install -r requirements.txt`
6. Start the dashboard: `streamlit run app.py`

## Dashboard modules
- Product profitability: product margin leaderboard, profit contribution chart, margin-risk queue
- Division performance: revenue vs profit and margin distribution by division
- Cost vs margin: cost-sales/profit scatter plots and risk flags
- Profit concentration: Pareto charts and top-five dependency indicators
- Filters: order date range, division, margin threshold slider, product name/ID search
- Data quality: missing values, duplicates, financial reconciliation and date checks

Gross margin is gross profit divided by sales. Flags are prompts for investigation, not automatic product-discontinuation recommendations.
