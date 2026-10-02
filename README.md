# Relay

> **Neighbors helping neighbors.**
>
> Relay turns scattered requests for help into coordinated community action.

Relay is a community assistance coordination platform designed to help communities coordinate practical assistance during local disruptions.

A requester can describe what they need in natural language. Relay structures the request, identifies suitable volunteers using an explainable matching engine, and guides the request through a two-sided completion workflow.

**Core workflow:**

`ASK → MATCH → ACT → RESOLVE`

## Live Application

**https://d1b0esm1k909vm.cloudfront.net**

The application is publicly reachable and deployed on AWS.

---

## What Relay Does

When something goes wrong in a community, people may need relatively simple but important assistance:

- Picking up medication
- Delivering food or water
- Transportation
- Mobility assistance
- Delivering supplies
- General community help

The challenge is turning an unstructured request into an actionable task and finding an appropriate available volunteer.

Relay addresses this through four stages.

### 1. ASK

A requester describes their need naturally.

For example:

> "My elderly parents need someone to pick up their prescription from the pharmacy."

Relay converts this into structured information such as:

- Category
- Urgency
- People affected
- Required skills
- Mobility needs
- Summary

### 2. MATCH

Relay identifies suitable volunteers using an explainable deterministic scoring model.

| Matching factor | Weight |
|---|---:|
| Skill match | 40% |
| Availability | 20% |
| Proximity | 25% |
| Workload | 10% |
| Urgency suitability | 5% |

The system uses approximate geographic coordinates and Haversine distance for proximity calculations.

### 3. ACT

A volunteer claims the request and the request progresses through:

`REQUESTED → CLAIMED → IN_PROGRESS → VOLUNTEER_COMPLETED`

### 4. RESOLVE

The requester confirms that the assistance was completed.

The request then becomes:

`RESOLVED`

This two-sided completion workflow distinguishes between someone offering to help and the requested assistance actually being confirmed as complete.

---

# AI + Deterministic Matching

Relay deliberately separates the AI problem from the decision problem.

AI is used to understand messy natural-language requests and convert them into structured assistance needs.

The volunteer matching itself is deterministic and explainable.

    Natural-language request
              ↓
         AI structuring
              ↓
    Structured assistance need
              ↓
      Deterministic matching
              ↓
       Suitable volunteers
              ↓
        Human coordination

This allows people to describe their needs naturally while keeping volunteer selection transparent and based on explicit criteria.

The application supports a pluggable request-structuring architecture, allowing deterministic local structuring and an optional Amazon Bedrock-backed implementation.

---

# Trust, Privacy & Safety

Relay is designed for community assistance. It is **not a replacement for emergency services**.

The application includes:

- Amazon Cognito authentication
- User profiles
- Volunteer profiles
- User-initiated approximate location sharing
- Privacy-conscious location handling
- Reporting and blocking
- Bidirectional blocking during matching
- Two-sided completion confirmation
- Emergency-service guidance

### Identity

Users authenticate through Amazon Cognito.

Backend identity is derived from the authenticated Cognito identity rather than trusting user identifiers supplied by the client.

### Location Privacy

Relay uses approximate location information for matching.

Exact coordinates are not exposed through the public request experience.

### Trust Limitations

Email verification establishes access to an account, but it does not prove that a request is genuine.

Relay therefore does not claim that AI can determine whether a request is truthful.

The platform instead combines authentication, privacy controls, reporting/blocking, explainable matching, and two-sided completion confirmation.

---

# Interactive Demo

Relay includes a frontend-only interactive demo for reviewers.

The demo allows someone to understand the complete workflow without creating an account:

`ASK → MATCH → ACT → RESOLVE`

The demo uses simulated data and does not create real requests or modify production data.

For the complete experience, users can register and participate as a requester or volunteer.

---

# AWS Architecture

Relay is deployed as a serverless AWS application.

    User
      │
      ▼
    Amazon CloudFront
      │
      ▼
    Amazon S3
    React Web App
      │
      ▼
    Amazon API Gateway
    JWT Authorizer
      │
      ▼
    AWS Lambda
    Relay API
      │
      ├──────────────┬──────────────┐
      ▼              ▼              ▼
    Amazon         Amazon       CloudWatch
    Cognito        DynamoDB      Monitoring
    Identity       Data Store
      │
      ▼
    AWS IAM
    Permissions

## AWS Services

### Amazon S3

Hosts the production frontend assets.

### Amazon CloudFront

Provides public HTTPS delivery for the Relay web application.

### Amazon API Gateway

Provides the HTTP API and JWT-protected application routes.

### AWS Lambda

Runs the Python backend without managing servers.

### Amazon DynamoDB

Stores application data including:

- Requests
- User profiles
- Volunteer profiles
- Reports
- Blocks
- Request lifecycle information

### Amazon Cognito

Provides user registration, authentication, email verification, and authenticated identity.

### Amazon CloudWatch

Provides application logging and monitoring.

### AWS IAM

Provides permissions between AWS services and the Lambda execution environment.

### OpenTofu / Terraform

Infrastructure is defined as code and deployed through the infrastructure configuration in this repository.

---

# Development with Codex + AWS Agent Toolkit

Relay was developed using **Codex** as the primary coding agent.

Codex was connected to AWS through the **AWS Agent Toolkit and AWS MCP** using OAuth authentication.

The coding agent was used throughout the development process to work across both application code and AWS infrastructure.

Examples of agent-assisted work include:

- Building the application foundation
- Implementing the request lifecycle
- Implementing request structuring
- Building the deterministic matching engine
- Implementing volunteer workflows
- Implementing authentication and identity handling
- Implementing trust and safety features
- Creating AWS infrastructure with OpenTofu/Terraform
- Inspecting AWS resources
- Troubleshooting AWS deployment issues
- Running automated tests
- Running frontend type checks and production builds
- Validating the deployed application
- Iterating against the live AWS environment

The AWS connection was used by the coding agent to inspect and interact with the AWS environment during development.

---

# Development Stages

The project was developed incrementally.

    Stage 1
    Application foundation
            ↓
    Stage 2
    Request lifecycle
            ↓
    Stage 3
    AI request structuring + volunteer matching
            ↓
    Stage 4
    AWS serverless deployment
            ↓
    Stage 5
    Identity + trust + safety
            ↓
    Final
    Reviewer demo + live verification

## Stage 1 — Foundation

Created the initial React frontend, Python backend, domain models, services, repositories, and infrastructure structure.

## Stage 2 — Request Lifecycle

Implemented:

- Request creation
- Request listing
- Request retrieval
- Status transitions
- Frontend request workflow
- Backend tests

## Stage 3 — Structuring + Matching

Implemented:

- Natural-language request structuring
- Pluggable structuring service
- Optional Bedrock adapter
- Volunteer profiles
- Deterministic matching
- Explainable matching reasons
- Volunteer claim workflow

## Stage 4 — AWS Deployment

Deployed the application using:

- Amazon S3
- Amazon CloudFront
- Amazon API Gateway
- AWS Lambda
- Amazon DynamoDB
- Amazon CloudWatch
- AWS IAM

The complete request lifecycle was tested against the live AWS deployment.

## Stage 5 — Identity, Trust & Safety

Expanded the application with:

- Amazon Cognito authentication
- User profiles
- Volunteer profiles
- Cognito-subject-based identity
- Approximate location handling
- Location privacy
- Reporting
- Blocking
- Two-sided completion
- JWT-protected API routes
- Reviewer-friendly demo experience

---

# Testing

The backend includes automated tests covering request behavior, structuring, matching, identity, and trust-related functionality.

Before deployment, the project was also validated through:

- Python compilation
- Backend automated tests
- Frontend TypeScript type checking
- Production frontend builds
- OpenTofu formatting and validation
- Terraform/OpenTofu planning
- Live AWS deployment testing

The final application was manually tested through the complete workflow:

    Create request
          ↓
    Structure request
          ↓
    Review and confirm
          ↓
    Find volunteer matches
          ↓
    Volunteer claims request
          ↓
    Volunteer starts helping
          ↓
    Volunteer marks completed
          ↓
    Requester confirms
          ↓
    Request resolved

---

# Repository Structure

    relay/
    ├── backend/
    │   ├── app/
    │   ├── tests/
    │   ├── local_server.py
    │   └── requirements.txt
    │
    ├── frontend/
    │   ├── src/
    │   ├── public/
    │   ├── package.json
    │   └── vite.config.ts
    │
    ├── infrastructure/
    │   ├── modules/
    │   ├── environments/
    │   └── README.md
    │
    ├── docs/
    │   ├── architecture.md
    │   ├── product.md
    │   └── development-log.md
    │
    ├── README.md
    └── .gitignore

---

# Local Development

The local development environment uses in-memory repositories and a development-only identity configuration. AWS credentials are not required for the basic local demo.

## Backend

    cd backend
    python3 local_server.py

The local backend runs on port `8000`.

## Frontend

In another terminal:

    cd frontend
    npm install
    npm run dev

Open the Vite URL shown in the terminal, usually:

    http://localhost:5173

The frontend proxies `/api` requests to the local backend.

Local request data is stored in process memory and is cleared when the backend stops.

---

# Running Tests

From the backend directory:

    cd backend
    python3 -m unittest discover -s tests -v

For frontend validation:

    cd frontend
    npm run typecheck
    npm run build

---

# Infrastructure

AWS infrastructure is defined using OpenTofu/Terraform under:

    infrastructure/

The infrastructure configuration manages the serverless AWS resources used by Relay.

Before making infrastructure changes, review:

    infrastructure/README.md
    docs/architecture.md

Do not commit AWS credentials, local credential files, access tokens, or secrets to the repository.

---

# Security

No AWS credentials or local credential files belong in this repository.

Sensitive values should be provided through the appropriate AWS authentication mechanisms or environment configuration and must not be committed to source control.

Do not commit:

- `.env` files containing secrets
- AWS credentials
- Cognito access tokens
- Terraform state containing sensitive data
- Local credential files

---

# Hackathon Submission

**AWS Zero to Shipped Hackathon — 2026**

**Category:** Social Good

**Focus Track:** Community

**Core workflow:** ASK → MATCH → ACT → RESOLVE

**Live Application:**

https://d1b0esm1k909vm.cloudfront.net

Relay was built and shipped on AWS using Codex connected to the AWS environment through the AWS Agent Toolkit and AWS MCP.

---

# Project Goal

When something goes wrong, information becomes fragmented.

Relay is built around a simple idea:

> **Turn fragmented requests into coordinated community action.**

Relay is not intended to replace emergency services or professional aid organizations.

Instead, it focuses on the everyday layer of community assistance where a neighbor or local volunteer can help another person complete a practical task.

---

# License

This project is licensed under the MIT License.

See [LICENSE](LICENSE) for details.