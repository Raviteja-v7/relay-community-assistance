# Relay AWS deployment

The Terraform root composes the existing API Gateway, Lambda, DynamoDB, S3, and CloudFront modules. The API uses a Python 3.12 Lambda and API Gateway HTTP API v2 proxy payloads. The Lambda zip contains the Relay application packages; boto3 is supplied by the Lambda Python runtime, while `backend/requirements.txt` remains for local DynamoDB use. The S3 frontend bucket stays private behind CloudFront Origin Access Control. CloudWatch retains Lambda and API access logs for 30 days, and the API Gateway default route is throttled to 20 requests per second with a burst limit of 40.

The Lambda runs the local deterministic request structurer by default (`RELAY_REQUEST_STRUCTURING=local`). DynamoDB stores requests, profiles, volunteers, reports, and blocks in one table using `PK` prefixes. AWS mode does not seed fictional volunteers. Cognito email verification and an API Gateway HTTP API JWT authorizer protect the API; `/health` remains public. The browser app uses a public OAuth client with authorization code + PKCE. No Bedrock permissions, EventBridge, or SNS resources are added.

Terraform publishes the Vite build from `../frontend/dist`. It replaces the local `config.js` with the API URL and Cognito public configuration, so the built frontend signs in through Cognito while local Vite development continues to use `/api` and a development-only identity header.

## Prepare and inspect

From the repository root:

```sh
npm --prefix frontend ci
npm --prefix frontend run typecheck
npm --prefix frontend run build
bash backend/package_lambda.sh
cd infrastructure
terraform init
terraform fmt -recursive
terraform validate
terraform plan -out=relay.tfplan
terraform show relay.tfplan
```

Review the full plan before applying it. Apply only after explicit approval:

```sh
terraform apply relay.tfplan
```

The default region is `us-east-1`; override it with `-var='aws_region=...'` or a local untracked `terraform.tfvars`. `terraform.tfvars.example` contains non-secret defaults. Terraform uses the standard local AWS credential chain; never place credentials in tfvars or this repository.

After apply, `terraform output` prints the API/CloudFront URLs, S3 bucket, DynamoDB table, Cognito pool/client IDs, and managed-login domain. The browser runtime config is uploaded by Terraform.

## Safety and limitations

- Stage 4 is deployed. Stage 5 changes are local only and have not been applied. Review the full Terraform plan; it should add Cognito and the JWT authorizer, modify API authorization/runtime config/Lambda permissions, and must not replace or destroy the existing API, Lambda, table, bucket, or CloudFront distribution.
- The frontend bucket and DynamoDB table have deletion protection (`prevent_destroy`; DynamoDB also enables service deletion protection). The bucket is private and configured not to force-delete objects.
- Terraform state is local by default and is ignored by git. Use a protected remote backend with locking before team or production use.
- The API uses a Cognito JWT authorizer. Email verification confirms account access only; it does not verify a request's truth.
- Local mode includes fictional demo volunteers and a development-only identity header. Lambda mode persists Cognito-subject volunteer profiles and does not seed demos.
- Public request/profile responses omit exact coordinates and addresses. Coordinates are rounded before storage; public neighborhood fields are generic. Reports persist, but no moderator review queue exists.
- Request and volunteer list operations scan the table, and request/volunteer changes are not transactionally atomic. This deployment is for a small hackathon MVP, not high-concurrency production use.
- API Gateway and Lambda access logs have 30-day retention. The current API access log format includes caller IP addresses.
- CloudFront uses its default `cloudfront.net` hostname and certificate. A custom domain is not configured.
