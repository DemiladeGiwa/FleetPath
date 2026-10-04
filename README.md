<p><img src="assets/fleetpath-logo.png" alt="FleetPath" width="360"></p>

# FleetPath

FleetPath is a free tool for small public-sector fleets (school districts, municipalities, transit agencies) comparing five fuel pathways on annualized cost and annual carbon: diesel, biodiesel (B20), battery-electric, hydrogen fuel cell, and CNG. It returns one verdict, the numbers behind it, and the source of every number.

It's a decision-support estimate, not a procurement quote.

## What it covers

| | |
|---|---|
| Vehicle classes | School bus (Type C), transit bus (40-ft) |
| Fleet owners | School district / board, municipality, public transit agency, private contractor |
| Canada | Quebec, Ontario, British Columbia, Alberta, New Brunswick |
| United States | California, Indiana, Texas, Washington |
| Pathways | Diesel, B20, battery-electric, hydrogen fuel cell, CNG |

A region only appears once it has a cited grid factor and fuel/electricity prices behind it. Nova Scotia is partly sourced and not selectable yet.

## How it works

- **Cost:** vehicle capital is spread over the holding period the fleet enters; infrastructure over 20 years. Both are added to one year of fuel and maintenance. Canadian results are in CAD: provincial diesel and electricity prices are native CAD, and US-only baselines are converted at a dated Bank of Canada rate.
- **Carbon:** annual tons CO2e from regional grid factors (EPA eGRID, ECCC NIR) and well-to-wheel fuel factors (Argonne GREET).
- **Verdict:** a blend of the cost and carbon scores. The default is 60% cost / 40% carbon, and the fleet can change it. If the winner costs more per year than diesel, the verdict says so. A payback is only reported if it lands inside the holding period.
- **Hydrogen:** two supply options are modeled, delivered liquid hydrogen and on-site electrolysis, and the cheaper one is reported. Canada's Clean Hydrogen ITC applies only to a private contractor's on-site electrolysis equipment, at the rate tier implied by its modeled carbon intensity.
- **Incentives:** Quebec's PETS rebate for electric school buses, the Clean Hydrogen ITC as above, and any grant the fleet enters. All of them reduce upfront capital.

Every parameter lives in `data/` with its source. Values without a published source carry the label "engineering estimate pending citation", and a test enforces this. The full method, sources and known limitations are in the FleetPath Methodology & Data Sources document.

## Run it locally

Requires Python 3.12+ and Node 20+.

```bash
# backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn api.main:app --port 8000

# frontend, in a second terminal
cd fleetpath-frontend
npm ci
npm run dev                        # http://localhost:5173
```

The frontend calls the API at `http://localhost:8000` by default. For a deployed API, build with `VITE_API_BASE=https://your-api-host npm run build`.

API:
- `POST /api/v1/calculate`: results as JSON
- `POST /api/v1/report`: one-page PDF
- `GET /api/v1/health`

## Tests

```bash
python -m pytest -q
```

## Data upkeep

`scripts/refresh_fx_snapshot.py` refreshes the Bank of Canada USD/CAD rate in `data/fx_rates.json`. A scheduled GitHub Action runs it on weekdays and opens a pull request when the rate changes.

## License

MIT. See [LICENSE](LICENSE).
