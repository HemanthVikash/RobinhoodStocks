# RobinhoodStocks

A full-stack Robinhood portfolio tracker with:
- a FastAPI backend (`server.py`) for portfolio/contribution endpoints
- a React + Vite frontend (`robinhood-app`) for charting and tab-based views
- pytest coverage for backend and client probe behavior

## Features

- Robinhood-authenticated backend session (with MFA support)
- Portfolio history endpoint: `GET /api/portfolio?tab=...`
- Top movers endpoint: `GET /api/contributions?tab=...`
- Health endpoint: `GET /api/ping`
- React UI with period tabs: `1D`, `1W`, `1M`, `3M`, `YTD`, `ALL`
- Frontend served by FastAPI from `robinhood-app/dist` in production-style runs

## Project Structure

```text
.
├── server.py
├── client_test.py
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   └── test_*.py
└── robinhood-app/
    ├── src/
    ├── package.json
    └── dist/ (created after build)
```

## Prerequisites

- Conda (Miniconda or Anaconda)
- Node.js 18+ and npm
- Robinhood account credentials (and optional TOTP secret for MFA)

## 1) Backend Setup (Conda)

From project root, create and activate the Conda environment using `environment.yaml`:

```bash
conda env create -f environment.yaml
conda activate robinhood-analysis
```

If the environment already exists and you updated dependencies:

```bash
conda env update -f environment.yaml --prune
conda activate robinhood-analysis
```

## 2) Frontend Setup

From `robinhood-app`:

```bash
npm install
npm run build
```

The build output is generated at `robinhood-app/dist`.

## 3) Run the App

From project root:

```bash
python server.py
```

You will be prompted for:
- email
- password
- optional MFA code or TOTP secret

After login, open:
- [http://localhost:8000](http://localhost:8000) for the UI
- [http://localhost:8000/api/ping](http://localhost:8000/api/ping) for health

## 4) Development Workflow (Optional)

If you want frontend hot reload while iterating on UI:

```bash
cd robinhood-app
npm run dev
```

Then run backend separately in another terminal:

```bash
python server.py
```

## 5) Run Tests

From project root:

```bash
pytest -q
```

Optional API probe against a running server:

```bash
python client_test.py --base-url http://localhost:8000
```

## 6) Access from Your Phone (Different Network)

Run backend locally, then expose port 8000 with a tunnel:

- Cloudflare quick tunnel:
  ```bash
  cloudflared tunnel --url http://localhost:8000
  ```
- or ngrok:
  ```bash
  ngrok http 8000
  ```

Open the generated HTTPS URL on your phone (cellular).

## Notes on Data Accuracy

- The backend first attempts authoritative Robinhood portfolio history.
- If unavailable, it falls back to a synthesized approximation from open positions and market data.
- When fallback is used, response includes warning metadata (`is_approximate`, `warning`).

## Security Notes

- Do not expose this service publicly without access control.
- Current default CORS is permissive (`*`) for local development convenience.
- Prefer tunnel auth (e.g., Cloudflare Access or ngrok auth) when sharing.

## Collaboration: Developers + Statisticians Wanted

Interested in improving this project? Contributions are welcome.

We are actively looking for:
- **Developers** to improve API reliability, auth/session handling, deployment, and UI polish
- **Statisticians / Quant-minded contributors** to improve return/P&L methodology, attribution logic, and model validation

Great first contribution ideas:
- improve long-horizon (`3M`, `YTD`, `ALL`) accuracy
- add order/transfer/dividend-aware performance attribution
- harden production deployment and auth
- expand test coverage with richer fixture scenarios

Open an issue or PR with your idea, approach, and test plan. If you have a quant/data background, include any assumptions and validation method so results are reproducible.

Feel free to reach out to me on [LinkedIn](https://www.linkedin.com/in/hemanth-vikash-kannan-rajan-b71063142/) or via email at [hemanth.rajan98@gmail.com](mailto:hemanth.rajan98@gmail.com) for any ideas on contibuting.
