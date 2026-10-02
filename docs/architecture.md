# Relay architecture

## Goals

- Coordinate everyday community assistance through a clear request and fulfillment workflow.
- Use AI only to turn freeform descriptions into reviewable structured request drafts.
- Keep volunteer matching deterministic and explainable.
- Keep API transport, business logic, and persistence behind separate boundaries.
- Build and verify locally before any AWS deployment.

## Authenticated API

All responses are JSON. Timestamps use UTC ISO format.

| Method and path | Purpose | Success |
| --- | --- | --- |
| `GET /health` | Local/runtime health | `200` |
| `POST /requests/structure` | Return a validated request draft from `{ "description": "..." }` | `200` |
| `POST /requests` | Persist a requester-confirmed structured request; owner comes from JWT `sub` | `201` |
| `GET /requests` | List requests | `200` |
| `GET /requests/{request_id}` | Fetch a request | `200` |
| `GET /volunteers` | List public volunteer fields only | `200` |
| `POST /requests/{request_id}/matches` | Structure legacy request data if needed and return ranked matches | `200` |
| `POST /requests/{request_id}/claim` | Claim as the authenticated available volunteer; client IDs are ignored | `200` |
| `PATCH /requests/{request_id}/status` | Claimed volunteer advances to in-progress or volunteer-completed | `200` |
| `POST /requests/{request_id}/confirm` | Request owner confirms receipt and resolves the request | `200` |
| `GET/PUT /me` | Read or save the authenticated profile | `200` |
| `GET/PUT /me/volunteer` | Read or save the caller's volunteer profile | `200` |
| `GET /me/blocks` | List accounts blocked by the caller | `200` |
| `POST/DELETE /users/{user_id}/block` | Block or unblock an account | `201` / `204` |
| `POST /reports` | Persist a report about a request or user | `201` |

All routes other than `GET /health` require a verified Cognito JWT in AWS. Backend identity comes only from API Gateway's verified `sub` claim. Validation failures return `400`, missing records `404`, ownership failures `403`, lifecycle conflicts `409`, and structuring failures `502`.

## Request understanding

`RequestStructuringService` is a protocol, so API and domain code do not depend on Bedrock. `LocalRequestStructuringService` uses deterministic keyword rules for local demo/test behavior; it makes no model call and does not imitate an AI response. `BedrockRequestStructuringService` uses the AWS SDK Bedrock Runtime Converse API with a forced tool call and a JSON input schema. The application validates the returned fields again: allowed category, urgency, skills, mobility values, positive people count, bounded summary, and no extra keys.

Bedrock is used for the narrow language-understanding task of mapping a person's description to normalized assistance fields. Structured categories and required skills make requests easier to confirm and match. Relay is still a coordination product, not a chatbot. The request creator sees and confirms a draft before it is saved. Raw Bedrock responses are never sent to the frontend, and model output cannot trigger a claim or status transition.

Configuration is through `RELAY_REQUEST_STRUCTURING=bedrock`, `RELAY_BEDROCK_MODEL_ID`, and `AWS_REGION`. The configured model must support Converse tool use. Credentials use the standard boto3 credential chain or an AWS runtime role. The model ID, region, and credentials are not hardcoded. No Bedrock call is required for local mode.

## Volunteer data

`User` includes `id`, `name`, `role`, point `location`, `skills`, `availability`, `activeRequests`, and `createdAt`. Roles are `REQUESTER`, `VOLUNTEER`, and `COORDINATOR`; availability is `AVAILABLE`, `BUSY`, or `OFFLINE`.

The local `InMemoryVolunteerRepository` seeds three deterministic fictional volunteers for local development. AWS mode does not seed them; real volunteer rows belong to authenticated Cognito subjects. `/me` stores account profiles at `PK=USER#{sub}` and volunteer rows use `PK=VOLUNTEER#{sub}`. Accounts can hold requester and volunteer roles; users can change only their own records.

## Deterministic matching

The matching engine filters out non-volunteers and anyone not `AVAILABLE`. It excludes blocked users in either direction and does not match the requester to their own request. It scores eligible candidates using these factors (maximum 100 points):

| Factor | Weight and calculation |
| --- | --- |
| Skill match | Up to 40 points, proportional to required skills matched. If no skills are required, the neutral score is 20. |
| Availability | 20 points for eligible `AVAILABLE` candidates. `BUSY` and `OFFLINE` volunteers are excluded. |
| Proximity | Up to 25 points from Haversine straight-line distance: ≤1 km = 25; ≤5 km = 20; ≤10 km = 15; ≤25 km = 8; farther or missing coordinates = 0. |
| Workload | `max(0, 10 - 2 × activeRequests)`. |
| Urgency suitability | Normal = 5. High = 5 at workload ≤1, 3 at ≤3, otherwise 0. Urgent = 5 with zero active requests, 3 with one, otherwise 0. |

Haversine uses an Earth radius of 6371.0088 km. It estimates straight-line proximity, not driving or walking distance. If either side has no coordinates, the match reports distance as unavailable and earns zero proximity points; it never invents a distance.

Results sort by score descending, then known distance ascending, volunteer name, and ID. Each result returns a score breakdown and reasons such as skill fit, availability, approximate distance, and workload. Matching stays deterministic so the factors are visible, debuggable, and testable; it does not use an opaque ML model.

## Claim and lifecycle

Authenticated requests follow `REQUESTED → CLAIMED → IN_PROGRESS → VOLUNTEER_COMPLETED → REQUESTER_CONFIRMED → RESOLVED`. The claiming volunteer marks help complete; only the request owner can confirm receipt. Confirmation writes both final transitions to `statusHistory` and sets `resolvedAt`, with current status `RESOLVED`. Legacy ownerless records retain their former volunteer-resolved transition. Claims use the caller's Cognito `sub` and require that subject's available volunteer profile.

## Storage and AWS configuration

`RequestService` depends on repository protocols. AWS mode uses boto3 adapters against the existing single DynamoDB table and unchanged string partition key `PK`: requests use `REQUEST#{request_id}`, profiles use `USER#{sub}`, volunteers use `VOLUNTEER#{sub}`, blocks use `BLOCK#{blockerSub}#{blockedSub}`, and reports use `REPORT#{reportId}`. No GSI or geospatial service is needed for the MVP. Small-board and block-list reads scan; exact block checks use point reads. AWS mode does not seed fictional volunteers.

Local mode uses `RELAY_STORAGE=memory` and deterministic structuring. The WSGI server enables a local-only demo identity header to switch between fictional users; this fallback is disabled in Lambda. AWS mode uses Cognito managed login with authorization code + PKCE, a public client without a secret, and an API Gateway HTTP API JWT authorizer. The `$default` route requires JWT and `/health` is explicitly public. Lambda continues to use DynamoDB and local deterministic structuring; no Bedrock permission is added.

## AWS deployment foundation

The Terraform root composes:

```text
Browser → CloudFront → private S3 bucket (frontend)
Browser → Cognito managed login (authorization code + PKCE)
Browser → API Gateway HTTP API v2 (JWT authorizer) → Lambda (app.api.handler.handler)
                                          ├─ DynamoDB request repository
                                          ├─ DynamoDB user/volunteer profiles
                                          └─ DynamoDB report/block records
API Gateway and Lambda → CloudWatch Logs (30-day retention)
Lambda execution role → least-privilege DynamoDB and CloudWatch permissions
```

CloudFront serves a private S3 origin through Origin Access Control. Terraform uploads the Vite build and a runtime `config.js` containing the API URL and Cognito public configuration. Local development retains its `/api` Vite proxy. API Gateway sends payload format 2.0 events to the existing Lambda-compatible handler. It applies JWT authorization on `$default`, with an explicit public health route, and owns browser preflight configuration. Terraform outputs the API/CloudFront URLs, S3 bucket, DynamoDB table, and Cognito IDs/domain.

The default request structurer remains deterministic and local. No Bedrock access, EventBridge, or SNS resources are added. Terraform files provide a deployment foundation but are not evidence of a completed deployment; apply only after reviewing and approving the plan.

## Frontend

The React client uses a typed API module. Vite proxies `/api` to the standard-library WSGI adapter on port 8000. The workflow is describe → review → confirm → match → claim → in progress → volunteer completion → requester confirmation. Browser location is requested only after an explicit user action. OAuth tokens stay in `sessionStorage`; authorization is enforced by the API Gateway authorizer and backend ownership checks.

## Safety and remaining scope

Relay is for everyday community assistance and local disruptions. It is not an emergency response service or a substitute for local emergency services. AI output is untrusted and validated; it cannot autonomously contact or assign volunteers. Location is optional and users can provide neighborhood text without coordinates.

Email verification confirms account access, not that a request is genuine. Coordinates are rounded to three decimal places (roughly 100 m) before persistence and removed from API responses. Other users see a generic approximate-area label and a generic request description; full text and exact neighborhood labels remain requester-only. Relay directs immediate danger to local emergency services and is not an emergency response service. A small keyword rule may show a warning, but it does not assess or verify emergencies. Relay does not grant pharmacy, medical, or legal authorization. Reports persist but no moderation queue exists. Volunteers do not yet receive private address/contact handoff after claiming. DynamoDB listing still scans; volunteer/request updates during claims are separate writes, so concurrent claims are not atomic. Cognito and JWT Terraform are implemented locally but not deployed. Remote locked Terraform state, alarms, moderation operations, and high-volume indexes remain future work.
