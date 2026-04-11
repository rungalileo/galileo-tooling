# Astra

Galileo dev bot.  Runs agent-enabled commands in a remote container.

<img src="assets/astra-logo-800x800.png" alt="Astra logo" width="200">

## Commands

- `review`: PR review

## Implementation

A CLI wrapping Claude Agent SDK workflows with Galileo-specific skills, tools and development environment setup.

The CLI is activated through an asynchronous command pipeline and runs in sandbox containers via GCP Cloud Tasks.

## Architecture

```mermaid
sequenceDiagram
    actor User
    participant GitHub
    participant Gateway as astra-gateway
    participant Queue as astra-task-queue<br/>(Cloud Tasks)
    participant Job as astra-job<br/>(Cloud Run Job)
    participant Claude as Claude API

    User->>GitHub: Comment "/astra review" on PR

    Note over GitHub,Gateway: 1st gateway invocation (POST /webhook)
    GitHub->>Gateway: Webhook (issue_comment event)
    Gateway->>Gateway: Validate HMAC signature
    Gateway->>Gateway: Parse command, extract PR metadata
    Gateway->>GitHub: Mint installation token, fetch head SHA
    Gateway->>GitHub: Add 👀 reaction (acknowledged)
    Gateway->>Queue: Enqueue task (repo, PR#, command, SHA)
    Gateway-->>GitHub: 200 OK (< 10s)

    Note over Queue,Gateway: 2nd gateway invocation (POST /dispatch)
    Queue->>Gateway: Deliver task with OIDC token
    Gateway->>Gateway: Validate OIDC token
    Gateway->>Job: Start execution (container overrides)
    Gateway-->>Queue: 200 OK

    Note over Job,GitHub: Job runs in fresh container
    Job->>Job: Mint GitHub installation token
    Job->>GitHub: Fetch PR diff & changed files
    Job->>Claude: Run agentic workflow
    Claude-->>Job: Review results
    Job->>GitHub: Post review comments
    Job->>Job: Exit 0
```

## Directory Structure

```
astra/
├── assets/                  # Logo and static assets
├── deployment/              # Deployment and provisioning scripts
├── gateway/                 # Webhook receiver + task dispatcher (Cloud Run service)
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── src/astra_gateway/
│   └── tests/
├── shared/                  # Shared utilities (GitHub auth) used by gateway and job
│   ├── pyproject.toml
│   └── src/astra_shared/
└── job/                     # Agentic workflow runner (Cloud Run job)
    ├── Dockerfile
    ├── pyproject.toml
    ├── src/astra/
    └── tests/
```

## Deployment

All deployment is scripted. Run scripts from `bots/astra/`.

### Scripts

| Script | Purpose | When to run |
|---|---|---|
| `deployment/provision_secrets.py` | Provisions GitHub App credentials + API keys in GCP Secret Manager | First-time setup, or when rotating secrets |
| `deployment/provision_infra.py` | Creates service accounts, IAM bindings, Artifact Registry, and Cloud Tasks queue | After secrets, or when infra config changes |
| `deployment/build_and_push.py` | Builds Docker images (linux/amd64) and pushes to Artifact Registry | After code changes |
| `deployment/deploy.py` | Deploys gateway service + job to Cloud Run with secrets and env vars | After building images |

### Deployment order

```bash
cd bots/astra

# 1. Provision secrets (first-time only, or when rotating)
uv run deployment/provision_secrets.py

# 2. Provision infrastructure (first-time only, or when config changes)
uv run deployment/provision_infra.py

# 3. Build and push Docker images
uv run deployment/build_and_push.py

# 4. Deploy to Cloud Run
uv run deployment/deploy.py
```

All scripts are idempotent and safe to re-run. For routine deployments (code changes only), just run steps 3 and 4.

Each script supports `--help` for options (e.g., `--gateway`/`--job` to target a single component, `--tag` for a specific image tag). All scripts accept `--yes` (`-y`) to skip the confirmation prompt.

### Updating after code changes

After making changes to gateway or job code, rebuild and redeploy:

```bash
cd bots/astra

# Rebuild and push only the changed component
uv run deployment/build_and_push.py --gateway   # gateway changes only
uv run deployment/build_and_push.py --job        # job changes only
uv run deployment/build_and_push.py              # both

# Deploy the new image
uv run deployment/deploy.py --gateway            # gateway only
uv run deployment/deploy.py --job                # job only
uv run deployment/deploy.py                      # both
```

To deploy a specific image tag instead of `latest`:

```bash
uv run deployment/deploy.py --tag abc1234
```

### Post-deploy: GitHub App webhook URL

After the first deploy, update the GitHub App webhook URL to the gateway URL printed by `deploy.py`:

1. Go to the GitHub App settings > General > Webhook URL at https://github.com/organizations/rungalileo/settings/apps/galileo-astra
2. Set it to `https://<gateway-url>/webhook`
3. Verify delivery on the Advanced tab

### GCP resources

| Type | Name | Description |
|---|---|---|
| **Secret** | `astra-webhook-secret` | HMAC secret for validating GitHub webhook payloads |
| **Secret** | `astra-app-id` | GitHub App ID |
| **Secret** | `astra-app-private-key` | GitHub App private key (PEM) |
| **Secret** | `astra-anthropic-api-key` | Anthropic API key for Claude Agent SDK |
| **Secret** | `astra-shortcut-api-token` | Shortcut API token (optional) |
| **Service account** | `astra-gateway` | Used by the gateway Cloud Run service |
| **Service account** | `astra-job` | Used by the job Cloud Run job |
| **Cloud Tasks queue** | `astra-task-queue` | Dispatches review jobs (region: `us-west1`) |
| **Cloud Run service** | `astra-gateway` | Receives GitHub webhooks and enqueues tasks |
| **Cloud Run job** | `astra-job` | Executes PR reviews in a sandboxed container |

## GitHub App

| Resource | URL |
|---|---|
| App Public Page | https://github.com/apps/galileo-astra |
| App Settings | https://github.com/organizations/rungalileo/settings/apps/galileo-astra |
| Permissions | https://github.com/organizations/rungalileo/settings/apps/galileo-astra/permissions |
| Webhook Deliveries | https://github.com/organizations/rungalileo/settings/apps/galileo-astra/advanced |
| Installations | https://github.com/organizations/rungalileo/settings/installations |

### Required permissions

#### Repository permissions

| Permission | Access level | Why |
|---|---|---|
| **Contents** | Read-only | Fetch file contents during review |
| **Checks** | Read & write | Read CI check results; create Astra's own Check Run |
| **Issues** | Read & write | Post comments on PRs, read conversation history, add reactions (`eyes`, `rocket`) |
| **Metadata** | Read-only | Automatically granted; basic repo info |
| **Pull requests** | Read & write | Fetch PR metadata and diffs; submit reviews via GraphQL `addPullRequestReview` |
| **Commit statuses** | Read-only | Read legacy commit status results |

All other permissions should be **No access**.

#### Event subscriptions

| Event | Why |
|---|---|
| **Issue comments** | Primary trigger — fires on `/astra review` comments on PRs |

## GCP Console

| Resource | URL |
|---|---|
| Artifact Registry | https://console.cloud.google.com/artifacts/docker/rungalileo-dev/us-west1/astra?project=rungalileo-dev |
| Secret Manager | https://console.cloud.google.com/security/secret-manager?referrer=search&project=rungalileo-dev |
| Cloud Run | https://console.cloud.google.com/run?project=rungalileo-dev |
| Cloud Tasks | https://console.cloud.google.com/cloudtasks?project=rungalileo-dev |
| Service Accounts | https://console.cloud.google.com/iam-admin/serviceaccounts?project=rungalileo-dev |
| Job Executions | https://console.cloud.google.com/run/jobs/details/us-west1/astra-job/executions?project=rungalileo-dev |
| Gateway Logs | https://console.cloud.google.com/run/detail/us-west1/astra-gateway/observability/logs?project=rungalileo-dev |
| Job Logs | https://console.cloud.google.com/run/jobs/details/us-west1/astra-job/observability/logs?project=rungalileo-dev |
| Logs Explorer | https://console.cloud.google.com/logs?project=rungalileo-dev |

## Why the name Astra?

Astra comes from the Latin word for “stars,” a nod to Galileo Galilei and his work observing the heavens.

The name reflects Galileo’s legacy of careful observation, discovery, and turning what we see into evidence.
