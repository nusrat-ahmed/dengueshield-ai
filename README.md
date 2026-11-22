# DengueShield AI
## Ward-Level Dengue Risk Outlook

DengueShield AI is a research prototype for generating ward-level dengue forecasts in Bangladesh. It combines historical dengue observations, weather variables, and ward-level vulnerability indicators to produce **2-week and 4-week prediction estimates**.

The application consists of a Python machine-learning pipeline, a FastAPI backend, and a Next.js frontend dashboard.

> **Research-use notice:** The supplied dataset ends on 29 December 2025. Forecasts are model-based estimates anchored to historical data. They are not live surveillance results, medical advice, or a substitute for official public-health decisions.

## Key capabilities

- Ward-level dengue case prediction for 2-week and 4-week horizons.
- Separate serialized model artifacts for each forecast horizon.
- Risk classification using thresholds stored in the corresponding model artifact.
- API responses containing predicted cases, risk level, selected weather inputs, risk thresholds, and risk-driver explanations.
- Interactive dashboard for selecting a city, ward, reference date, and forecast horizon.
- Local model inference through the FastAPI service.

## Dataset overview

The project dataset contains:

- **31,320** ward-date records.
- **5** cities: Chattogram, Dhaka North, Dhaka South, Gazipur, and Narayanganj.
- **60** wards.
- Date range: **4 January 2016 to 29 December 2025**.
- No missing values and no duplicate ward-date records in the reported dataset validation.

## Risk classification

The current model artifacts contain these thresholds:

| Risk category | Classification rule |
|---|---|
| LOW | Prediction is less than or equal to 5 |
| MEDIUM | Prediction is greater than 5 and less than or equal to 9 |
| HIGH | Prediction is greater than 9 and less than or equal to 14 |
| CRITICAL | Prediction is greater than 14 |

The backend reads these values from each `.joblib` artifact. Keep the artifact thresholds and backend classification logic consistent.

## Technology stack

| Layer | Technology |
|---|---|
| Machine learning and data processing | Python, pandas, NumPy, scikit-learn, Joblib |
| Backend API | FastAPI, Uvicorn, Pydantic |
| Frontend | Next.js, React, TypeScript |
| Dataset format | Excel workbook |
| Model artifact format | Joblib |

## Repository layout

```text
dengueshield-ai/
├── backend/
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── services/
│       │   └── predictor.py
│       └── ...
├── data/
│   └── ...
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── package.json
│   └── package-lock.json
├── ml/
│   └── features.py
├── models/
│   ├── dengue_2week.joblib
│   ├── dengue_4week.joblib
│   └── training_metrics.json
├── requirements.txt
├── README.md
└── ARCHITECTURE.md
```

## Prerequisites

- Git
- Python 3.10 or later (use the Python version supported by the installed project dependencies)
- Node.js and npm compatible with the Next.js version declared in `frontend/package.json`

## Local setup

### 1. Clone the repository

```powershell
git clone https://github.com/nusrat-ahmed/dengueshield-ai.git
cd dengueshield-ai
```

### 2. Create and activate the Python environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Start the backend

Run this command from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Open the API documentation:

- API documentation: http://127.0.0.1:8000/docs
- OpenAPI schema: http://127.0.0.1:8000/openapi.json

If port 8000 is unavailable, identify and stop the process using that port or select another available port. Do not start multiple backend instances on the same port.

### 4. Configure the frontend

Create or update `frontend/.env.local` using the API base URL expected by the frontend code. The usual local value is:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Confirm that the variable name matches the one referenced in `frontend/lib` before saving it.

### 5. Start the frontend

Open a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open the local URL printed by the Next.js terminal. It is commonly http://localhost:3000. If that port is occupied, Next.js may use another port; use the address printed in the terminal.

## Validation

### Frontend type checking

Run from the `frontend` directory:

```powershell
npm run typecheck
```

### Backend API tests

Open http://127.0.0.1:8000/docs and use the live Swagger schema. Submit separate `POST /predict` requests with `horizon_weeks` set to `2` and `4`.

Example request for the 2-week model:

```json
{
  "city": "Chattogram",
  "ward_id": "CCC_Ward_01",
  "horizon_weeks": 2,
  "as_of_date": "2025-12-29"
}
```

For the 4-week model, change `horizon_weeks` to `4`. Use the exact request schema displayed by the running API if it differs.

The expected response should include `predicted_cases`, `risk_level`, `horizon_weeks`, `risk_thresholds`, and `model_name`.

### Production build

Run from `frontend`:

```powershell
npm run build
```

A production build may require more available memory than the development server or TypeScript check. A previous build attempt on a machine with approximately 3.7 GB RAM ended with a Node.js out-of-memory error. Treat that as an environment resource limitation unless a separate build error is reported.

## Model evaluation

The repository includes `models/training_metrics.json`. Use this file as the source of truth for the recorded validation and test metrics. Do not manually retype performance values into documentation if the metrics artifact changes.

## Limitations

- The dataset is historical and ends on 29 December 2025.
- Forecasts are model estimates, not confirmed future case counts.
- Live weather and live dengue surveillance feeds should not be assumed unless separately integrated and verified.
- Risk-driver explanations describe selected elevated inputs; they do not establish causation.
- The prototype is intended for research and demonstration, not autonomous public-health decisions.

## Security and repository hygiene

- Do not commit `.env`, `.env.local`, API keys, passwords, access tokens, or other secrets.
- Keep `node_modules/`, `.next/`, `.venv/`, Python cache files, and temporary build outputs out of Git.
- Keep `package-lock.json` committed when using npm so collaborators install a consistent dependency tree.
- Do not replace `frontend/package.json` with a guessed file. Preserve the scripts and dependency versions already used by the working frontend.
