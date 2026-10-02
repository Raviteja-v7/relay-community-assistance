# Relay

Relay is a community assistance coordination platform. It turns an unstructured request for help into a structured request, finds suitable nearby volunteers, and tracks fulfillment.

This repository contains the Relay request, structuring, explainable matching, authentication, trust/safety, and completion workflows. Stage 4 is deployed; Stage 5 Cognito/API changes are local only and have not been applied.

## Project layout

- `frontend/` — React, TypeScript, and Vite request-to-match workflow
- `backend/` — Python Lambda-compatible API, domain models, services, and repositories
- `infrastructure/` — Terraform deployment root and AWS modules
- `docs/` — product, architecture, and development notes

## Local development

The local demo uses in-memory repositories and a development-only identity switch; it does not need AWS credentials. Start the backend and frontend in separate terminals.

Backend:

```sh
cd backend
python3 local_server.py
```

Frontend:

```sh
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (usually `http://localhost:5173`). Vite proxies `/api` requests to the local backend on port 8000. Requests live in backend process memory and clear when it stops.

Run backend tests:

```sh
cd backend
python3 -m unittest discover -s tests -v
```

Optional Bedrock structuring can run with local in-memory request storage by setting `RELAY_REQUEST_STRUCTURING=bedrock`, `RELAY_BEDROCK_MODEL_ID`, and `AWS_REGION` before starting the backend. Boto3 uses the standard credential chain; the account must have Bedrock model access. Local deterministic structuring is the default.

Optional DynamoDB storage requires `python3 -m pip install -r backend/requirements.txt`, `RELAY_STORAGE=dynamodb`, `RELAY_REQUESTS_TABLE`, and `AWS_REGION`. It stores requests, Cognito-subject profiles, volunteer profiles, reports, and blocks in the existing single table. AWS mode does not seed fictional volunteers. The Cognito/API Terraform configuration is not deployed yet.

No AWS credentials or local credentials files belong in this repository. For AWS deployment preparation, read [the Terraform deployment guide](infrastructure/README.md) and review [the architecture](docs/architecture.md). Review the full Stage 5 plan before any apply; Stage 5 has not been applied.

Read [the product brief](docs/product.md), [architecture](docs/architecture.md), and [development log](docs/development-log.md) before implementing features.
