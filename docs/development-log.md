# Development log

## 2026-10-02 — Foundation

- Inspected the repository; the workspace was empty.
- Added a React/TypeScript/Vite frontend shell with a responsive community-focused landing page.
- Added Python backend packages separating API, models, services, and repositories.
- Added Terraform root configuration and module placeholders for the requested AWS services. No resources were created.
- Documented product scope, initial entities, lifecycle, AI boundaries, deterministic matching, and the proposed AWS architecture.
- Added repository ignores for generated files and local secrets/credentials.

## 2026-10-02 — First local vertical slice

- Implemented the request API routes: health, create, list, detail, and status patch.
- Added input validation, generated request IDs, UTC timestamps, and sequential lifecycle transitions.
- Added an in-memory repository for local use and an isolated boto3 DynamoDB adapter using `PK = REQUEST#{request_id}`.
- Added a standard-library WSGI server and a Vite `/api` development proxy.
- Replaced the landing page with the request form, community request list, status badges, loading/error/empty states, and typed API client.
- Added 14 backend unit/API tests; `python3 -m unittest discover -s tests -v` passed.
- Frontend typecheck/build could not run because dependencies are not installed and npm registry DNS resolution failed (`ENOTFOUND registry.npmjs.org`). The local HTTP server could not bind a port in this restricted environment (`PermissionError`); the WSGI adapter and Lambda handler workflow were verified in-process for health, create, list, detail, and status update.

## 2026-10-02 — Request understanding and volunteer matching

- Added the `RequestStructuringService` protocol, deterministic local structurer, and Bedrock Runtime Converse adapter with a forced tool schema and application-side output validation.
- Extended `User` with role, point location, skills, availability, active workload, and creation timestamp. Added three deterministic fictional volunteers for local/demo use.
- Extended requests with the structured summary, required skills, mobility needs, structured marker, claimant, and resolution timestamp.
- Implemented explainable deterministic skill, availability, Haversine proximity, workload, and urgency scores with stable tie breaks.
- Added `POST /requests/structure`, `GET /volunteers`, `POST /requests/{id}/matches`, and `POST /requests/{id}/claim`; status updates now enforce the claim → in-progress → resolved flow.
- Reworked the frontend into describe → review → confirm → find matches, with match explanations and volunteer demo actions for claim/status changes.
- Added structuring boundary, scoring, availability, ranking, claim, duplicate claim, lifecycle, and API tests. `python3 -m unittest discover -s tests -v` passed all 32 tests.
- Bedrock was not invoked; adapter request shape and response validation were tested with a fake client. No AWS resources were created or deployed.
- Frontend typecheck and production build pass with `npm run typecheck` and `npm run build`; `frontend/package-lock.json` now records the installed dependency tree.
- The complete WSGI workflow passed in-process. The restricted environment also denied binding the Vite dev server (`listen EPERM`), so no browser session was available here.

## 2026-10-02 — AWS deployment foundation

- Inspected the Terraform root and the API Gateway, Lambda, DynamoDB, S3, and CloudFront module directories; they were placeholders and there was no local Terraform state or saved plan.
- Used the AWS MCP to inspect enabled regions and existing Lambda, DynamoDB, API Gateway, CloudWatch Logs, S3, CloudFront, and IAM resources. No Relay-named resources were found.
- Implemented Terraform for HTTP API Gateway v2, Python Lambda with least-privilege IAM, a protected on-demand DynamoDB single table, a private S3 frontend bucket, CloudFront OAC, and CloudWatch log groups. No Cognito, Bedrock, EventBridge, or SNS resources were added.
- Added Lambda packaging and a frontend runtime config object that Terraform fills with the API Gateway URL. Public API response contracts and deterministic structuring/matching behavior remain unchanged.
- Added a DynamoDB volunteer adapter sharing the request table so seeded volunteer availability/workload persists across Lambda instances and match/claim routes remain operational in AWS mode.
- `tofu fmt -recursive` passed. All 32 backend tests passed, and frontend typecheck/build passed. `bash backend/package_lambda.sh` produced the Lambda zip.
- Terraform is not installed in this environment. OpenTofu is installed, but `tofu init` could not download the AWS provider because DNS/network access to the OpenTofu registry is blocked. Provider-backed validate and plan did not run, and no AWS resources were applied.

## Next

## 2026-10-02 — Stage 5 foundation (not deployed)

- Added Cognito-subject identity extraction from API Gateway JWT claims, request ownership on newly created requests, claimant-only status changes, and protection against trusting body-supplied requester/volunteer IDs.
- Added persisted user and volunteer profile adapters using `USER#{sub}` and `VOLUNTEER#{sub}` in the existing DynamoDB table. AWS mode no longer seeds fictional volunteers; local memory mode retains them.
- Rounded coordinates to three decimal places before storage and removed exact coordinates and Cognito subjects from request/volunteer API serializers. Matching still uses the existing Haversine calculation and weights.
- Added volunteer-completed/requester-confirmed resolution, status history, reports, blocks, reverse-direction match exclusion, and corresponding UI actions.
- Added Cognito managed-login authorization code + PKCE frontend flow, email registration/verification through Cognito, JWT API calls, profile setup, volunteer settings, explicit browser geolocation request, and emergency-service messaging.
- Implemented Terraform for a Cognito User Pool, public web client/domain, API Gateway JWT authorizer with a public health route, Lambda DynamoDB delete permission, and runtime Cognito configuration. No AWS resources were created or changed.
- AWS MCP confirmed the existing HTTP API has an unauthenticated `$default` route with no authorizer; it supports adding a JWT authorizer without replacing the API. The existing DynamoDB table remains `PK`-only with deletion protection and PITR. The proposed Cognito domain prefix is unused.
- Backend: all 42 tests pass; Python compile check passes. Frontend: `npm run typecheck` and `npm run build` pass. `tofu fmt -check -recursive` passes.
- Terraform provider-backed validation/plan could not run: `tofu init -backend=false` could not resolve `registry.opentofu.org`; the cached AWS provider binary then failed the OpenTofu plugin handshake during both `tofu validate` and `tofu plan`. No apply was run. Stage 5 has not been deployed.

Before any AWS deployment, run `tofu init`, `tofu validate`, and `tofu plan` in an environment with provider registry access, review the plan for changes/replacements, and request explicit approval before applying it. Remaining operational work includes a moderator review process, atomic request/volunteer claim updates, production-grade Terraform state locking, and a public end-to-end Cognito smoke test after deployment.
