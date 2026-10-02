# Relay product brief

## Purpose

Relay helps a community turn a neighbor's request into practical, trackable support. It structures a freeform description, suggests nearby available volunteers with clear reasons, and tracks the request through fulfillment.

## Hackathon focus

- Category: Social Good
- Lane: Community
- Deliver a polished, working MVP that can later be made publicly accessible on AWS.
- AI supports request intake; Relay is a coordination product, not a general chatbot.

## MVP workflow

1. A signed-in requester describes the need in their own words and may share a neighborhood and optional approximate coordinates.
2. A request-structuring service proposes category, urgency, people affected, required skills, mobility needs, and a short summary.
3. The requester reviews and confirms the structured draft.
4. Relay saves the request and deterministically ranks available volunteers with explanations.
5. A signed-in volunteer claims the request, marks help complete, and the requester confirms receipt before it resolves.

Bedrock is reserved for extracting normalized request fields from natural language. It helps translate a description into a useful category and skills for the matching workflow. Model output is untrusted: the backend validates types and allowlists, and the requester confirms the draft before persistence. Local mode uses deterministic keyword rules and does not call a model.

## Stage 5 account and safety behavior

- A Cognito account can hold requester and volunteer roles. Volunteer profile, skills, availability, and approximate location are stored in DynamoDB under that account's `sub`.
- Browser geolocation runs only after an explicit user action. Coordinates are rounded to three decimal places before storage and never returned by request/profile APIs. Other users see neighborhood labels and approximate Haversine distance.
- Users can report requests or profiles, block/unblock accounts, and blocked pairs are excluded from matching in either direction.
- Relay displays an emergency-services warning. It does not use AI to determine whether a request is true or an emergency.
- A local keyword notice can flag emergency-like wording, but it is not an emergency assessment and can miss situations. Volunteers see generic request details; secure address/contact handoff is not implemented yet.
- Relay does not grant pharmacy, medical, or legal authorization to users.

Matching stays deterministic. Its score uses skill match (40 points), availability (20), straight-line proximity (25), workload (10), and urgency suitability (5), with a reason list and factor breakdown. Users can see why someone ranked highly. It does not claim to estimate actual travel time or route distance.

Relay supports everyday community assistance and local disruptions. It is not an emergency response service and does not replace local emergency services.

## Initial entities

### User

| Field | Meaning |
| --- | --- |
| `id` | Stable user identifier |
| `name` | Display name |
| `role` | `REQUESTER`, `VOLUNTEER`, or `COORDINATOR` |
| `location` | Label and optional latitude/longitude |
| `skills` | Volunteer skills or capabilities |
| `availability` | `AVAILABLE`, `BUSY`, or `OFFLINE` |
| `activeRequests` | Current claimed/in-progress requests |
| `createdAt` | Account creation time |

### Request

| Field | Meaning |
| --- | --- |
| `id` | Stable request identifier |
| `requesterId` | User who created the request (future authenticated flow) |
| `description` | Original human-readable need |
| `category` | Normalized request category |
| `urgency` | Normalized urgency |
| `location` | Neighborhood and optional coordinates |
| `peopleAffected` | Number of people needing support |
| `requiredSkills` | Volunteer skills required |
| `mobilityNeeds` | `none`, `limited`, `significant`, or `unknown` |
| `summary` | Short structured description |
| `status` | Current lifecycle state |
| `createdAt` | Request creation time |
| `claimedBy` | Volunteer user ID when claimed |
| `resolvedAt` | Resolution time when resolved |

### Match

| Field | Meaning |
| --- | --- |
| `id` | Stable match identifier |
| `requestId` | Request being matched |
| `volunteerId` | Candidate volunteer |
| `score` | Deterministic ranking score |
| `reasons` | Human-readable score explanation |
| `createdAt` | Match calculation time |

## Request lifecycle

`REQUESTED → CLAIMED → IN_PROGRESS → VOLUNTEER_COMPLETED → REQUESTER_CONFIRMED → RESOLVED`

The claiming volunteer marks the help complete; only the requester can confirm it was received. Confirmation records `REQUESTER_CONFIRMED` and `RESOLVED` in status history, with `RESOLVED` as current status. In AWS, Cognito email verification and the API Gateway JWT authorizer authenticate accounts. Email verification confirms account access, not request truth.

## Local and AWS modes

Local mode uses process-memory storage, deterministic rule-based structuring, fictional seed volunteers, and an explicitly local-only identity switch. It needs no AWS credentials. AWS mode uses Cognito accounts, API Gateway JWT validation, and DynamoDB request/profile/volunteer/report/block records. Cognito and API Gateway Terraform changes are prepared locally but have not been applied.

## MVP exclusions

No general conversational assistant, payments, multi-organization administration, automated dispatch, notifications, moderation queue, or emergency response. Stage 5 Cognito and API changes are implemented in Terraform but have not been deployed.
