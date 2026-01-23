# Docker Registry Setup Guide

This guide documents how to set up Docker image registries (AWS ECR and Google GCR) for the Micro-Alpha News Scraper project, including GitHub Actions integration for automated CI/CD deployments.

---

## Table of Contents

1. [Overview](#overview)
2. [AWS Elastic Container Registry (ECR)](#aws-elastic-container-registry-ecr)
3. [Google Container Registry (GCR)](#google-container-registry-gcr)
4. [GitHub Actions Integration](#github-actions-integration)
5. [Multi-Architecture Builds](#multi-architecture-builds)
6. [Security Best Practices](#security-best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Overview

### Why Use a Container Registry?

Container registries provide:
- **Version control** for Docker images
- **Secure storage** with access controls
- **Integration** with orchestration platforms (EKS, GKE, etc.)
- **Vulnerability scanning** for container security
- **Automated builds** via CI/CD pipelines

### Project Images

The Micro-Alpha project produces the following Docker images:

| Image | Description | Build Context |
|-------|-------------|---------------|
| `news-scraper/api` | FastAPI backend | `./backend` |
| `news-scraper/frontend` | Next.js frontend | `./frontend` |
| `news-scraper/celery-worker` | Celery worker | `./backend` |

---

## AWS Elastic Container Registry (ECR)

### Prerequisites

- AWS CLI installed and configured
- IAM user with ECR permissions
- Docker installed locally

### Step 1: Create ECR Repositories

Create a repository for each image:

```bash
# Set your AWS region
export AWS_REGION=us-east-1

# Create repositories
aws ecr create-repository \
    --repository-name news-scraper/api \
    --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=AES256 \
    --region $AWS_REGION

aws ecr create-repository \
    --repository-name news-scraper/frontend \
    --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=AES256 \
    --region $AWS_REGION

aws ecr create-repository \
    --repository-name news-scraper/celery-worker \
    --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=AES256 \
    --region $AWS_REGION
```

### Step 2: Configure Repository Policies

Set up lifecycle policies to manage image retention:

```bash
# Create lifecycle policy JSON
cat > ecr-lifecycle-policy.json << 'EOF'
{
    "rules": [
        {
            "rulePriority": 1,
            "description": "Keep last 10 production images",
            "selection": {
                "tagStatus": "tagged",
                "tagPrefixList": ["v", "release"],
                "countType": "imageCountMoreThan",
                "countNumber": 10
            },
            "action": {
                "type": "expire"
            }
        },
        {
            "rulePriority": 2,
            "description": "Delete untagged images older than 7 days",
            "selection": {
                "tagStatus": "untagged",
                "countType": "sinceImagePushed",
                "countUnit": "days",
                "countNumber": 7
            },
            "action": {
                "type": "expire"
            }
        },
        {
            "rulePriority": 3,
            "description": "Keep last 30 development images",
            "selection": {
                "tagStatus": "tagged",
                "tagPrefixList": ["dev", "main", "sha-"],
                "countType": "imageCountMoreThan",
                "countNumber": 30
            },
            "action": {
                "type": "expire"
            }
        }
    ]
}
EOF

# Apply to all repositories
for repo in api frontend celery-worker; do
    aws ecr put-lifecycle-policy \
        --repository-name news-scraper/$repo \
        --lifecycle-policy-text file://ecr-lifecycle-policy.json \
        --region $AWS_REGION
done
```

### Step 3: Authenticate Docker with ECR

```bash
# Get login command and authenticate
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    $(aws sts get-caller-identity --query Account --output text).dkr.ecr.$AWS_REGION.amazonaws.com
```

### Step 4: Build and Push Images

```bash
# Set variables
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
IMAGE_TAG=$(git rev-parse --short HEAD)

# Build and push API image
docker build -t $ECR_REGISTRY/news-scraper/api:$IMAGE_TAG ./backend
docker push $ECR_REGISTRY/news-scraper/api:$IMAGE_TAG

# Build and push frontend image
docker build -t $ECR_REGISTRY/news-scraper/frontend:$IMAGE_TAG ./frontend
docker push $ECR_REGISTRY/news-scraper/frontend:$IMAGE_TAG

# Tag as latest
docker tag $ECR_REGISTRY/news-scraper/api:$IMAGE_TAG $ECR_REGISTRY/news-scraper/api:latest
docker push $ECR_REGISTRY/news-scraper/api:latest
```

### IAM Policy for CI/CD

Create an IAM policy for GitHub Actions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ECRAuthToken",
            "Effect": "Allow",
            "Action": "ecr:GetAuthorizationToken",
            "Resource": "*"
        },
        {
            "Sid": "ECRPushPull",
            "Effect": "Allow",
            "Action": [
                "ecr:BatchCheckLayerAvailability",
                "ecr:BatchGetImage",
                "ecr:CompleteLayerUpload",
                "ecr:GetDownloadUrlForLayer",
                "ecr:InitiateLayerUpload",
                "ecr:PutImage",
                "ecr:UploadLayerPart"
            ],
            "Resource": [
                "arn:aws:ecr:*:*:repository/news-scraper/*"
            ]
        }
    ]
}
```

---

## Google Container Registry (GCR)

### Prerequisites

- Google Cloud SDK (gcloud) installed
- GCP project with billing enabled
- Docker installed locally

### Step 1: Enable Container Registry API

```bash
# Set your project
export GCP_PROJECT=your-project-id

gcloud config set project $GCP_PROJECT

# Enable the Container Registry API
gcloud services enable containerregistry.googleapis.com

# For Artifact Registry (recommended over Container Registry)
gcloud services enable artifactregistry.googleapis.com
```

### Step 2: Create Artifact Registry Repository (Recommended)

Artifact Registry is Google's next-generation container registry:

```bash
# Create repository
gcloud artifacts repositories create news-scraper \
    --repository-format=docker \
    --location=us-central1 \
    --description="News Scraper Docker images"

# List repositories
gcloud artifacts repositories list
```

### Step 3: Authenticate Docker with GCR

```bash
# Configure Docker to use gcloud as a credential helper
gcloud auth configure-docker

# For Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev
```

### Step 4: Build and Push Images

**Using Container Registry (gcr.io):**

```bash
# Set variables
GCR_REGISTRY=gcr.io/$GCP_PROJECT
IMAGE_TAG=$(git rev-parse --short HEAD)

# Build and push API image
docker build -t $GCR_REGISTRY/news-scraper-api:$IMAGE_TAG ./backend
docker push $GCR_REGISTRY/news-scraper-api:$IMAGE_TAG

# Build and push frontend image
docker build -t $GCR_REGISTRY/news-scraper-frontend:$IMAGE_TAG ./frontend
docker push $GCR_REGISTRY/news-scraper-frontend:$IMAGE_TAG
```

**Using Artifact Registry (Recommended):**

```bash
# Set variables
AR_REGISTRY=us-central1-docker.pkg.dev/$GCP_PROJECT/news-scraper
IMAGE_TAG=$(git rev-parse --short HEAD)

# Build and push API image
docker build -t $AR_REGISTRY/api:$IMAGE_TAG ./backend
docker push $AR_REGISTRY/api:$IMAGE_TAG

# Build and push frontend image
docker build -t $AR_REGISTRY/frontend:$IMAGE_TAG ./frontend
docker push $AR_REGISTRY/frontend:$IMAGE_TAG
```

### Service Account for CI/CD

Create a service account with minimal permissions:

```bash
# Create service account
gcloud iam service-accounts create github-actions-deployer \
    --display-name="GitHub Actions Deployer"

# Grant Artifact Registry Writer role
gcloud projects add-iam-policy-binding $GCP_PROJECT \
    --member="serviceAccount:github-actions-deployer@$GCP_PROJECT.iam.gserviceaccount.com" \
    --role="roles/artifactregistry.writer"

# Create and download key (store securely!)
gcloud iam service-accounts keys create github-actions-key.json \
    --iam-account=github-actions-deployer@$GCP_PROJECT.iam.gserviceaccount.com

# IMPORTANT: Store the contents of this file as a GitHub secret
# then delete the local file
cat github-actions-key.json
rm github-actions-key.json
```

---

## GitHub Actions Integration

### AWS ECR Workflow

Create `.github/workflows/docker-build-ecr.yml`:

```yaml
name: Build and Push to ECR

on:
  push:
    branches: [main]
    tags: ['v*']
  pull_request:
    branches: [main]

env:
  AWS_REGION: us-east-1

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Extract metadata for Docker
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: |
            ${{ steps.login-ecr.outputs.registry }}/news-scraper/api
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=sha,prefix=sha-

      - name: Build and push API image
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build and push Frontend image
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: ${{ github.event_name != 'pull_request' }}
          tags: |
            ${{ steps.login-ecr.outputs.registry }}/news-scraper/frontend:${{ github.sha }}
            ${{ steps.login-ecr.outputs.registry }}/news-scraper/frontend:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Google GCR/Artifact Registry Workflow

Create `.github/workflows/docker-build-gcr.yml`:

```yaml
name: Build and Push to GCR

on:
  push:
    branches: [main]
    tags: ['v*']
  pull_request:
    branches: [main]

env:
  GCP_PROJECT: your-project-id
  GAR_LOCATION: us-central1
  REPOSITORY: news-scraper

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Authenticate to Google Cloud
        id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2

      - name: Configure Docker for Artifact Registry
        run: |
          gcloud auth configure-docker ${{ env.GAR_LOCATION }}-docker.pkg.dev --quiet

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Extract metadata for Docker
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: |
            ${{ env.GAR_LOCATION }}-docker.pkg.dev/${{ env.GCP_PROJECT }}/${{ env.REPOSITORY }}/api
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=sha,prefix=sha-

      - name: Build and push API image
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build and push Frontend image
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: ${{ github.event_name != 'pull_request' }}
          tags: |
            ${{ env.GAR_LOCATION }}-docker.pkg.dev/${{ env.GCP_PROJECT }}/${{ env.REPOSITORY }}/frontend:${{ github.sha }}
            ${{ env.GAR_LOCATION }}-docker.pkg.dev/${{ env.GCP_PROJECT }}/${{ env.REPOSITORY }}/frontend:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Required GitHub Secrets

| Secret | Description | Platform |
|--------|-------------|----------|
| `AWS_ROLE_ARN` | IAM role ARN for OIDC authentication | AWS |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Workload Identity Federation provider | GCP |
| `GCP_SERVICE_ACCOUNT` | Service account email | GCP |

---

## Multi-Architecture Builds

Build images for both AMD64 and ARM64 (useful for Apple Silicon and AWS Graviton):

```yaml
# Add to your workflow
- name: Set up QEMU
  uses: docker/setup-qemu-action@v3

- name: Build and push multi-arch
  uses: docker/build-push-action@v5
  with:
    context: ./backend
    platforms: linux/amd64,linux/arm64
    push: true
    tags: ${{ steps.meta.outputs.tags }}
```

---

## Security Best Practices

### 1. Image Scanning

Enable vulnerability scanning on both platforms:

**AWS ECR:**
```bash
aws ecr put-image-scanning-configuration \
    --repository-name news-scraper/api \
    --image-scanning-configuration scanOnPush=true
```

**GCP Artifact Registry:**
```bash
gcloud artifacts repositories update news-scraper \
    --location=us-central1 \
    --enable-vulnerability-scanning
```

### 2. Use Workload Identity (No Long-Lived Credentials)

**AWS OIDC Setup:**
```bash
# Create OIDC provider for GitHub Actions
aws iam create-open-id-connect-provider \
    --url https://token.actions.githubusercontent.com \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

**GCP Workload Identity Federation:**
```bash
# Create workload identity pool
gcloud iam workload-identity-pools create github-pool \
    --location="global" \
    --display-name="GitHub Actions Pool"

# Create provider
gcloud iam workload-identity-pools providers create-oidc github-provider \
    --location="global" \
    --workload-identity-pool="github-pool" \
    --display-name="GitHub OIDC Provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
    --issuer-uri="https://token.actions.githubusercontent.com"
```

### 3. Minimal Base Images

Use distroless or Alpine-based images when possible:

```dockerfile
# Use multi-stage builds with minimal runtime images
FROM python:3.11-slim AS builder
# ... build steps ...

FROM gcr.io/distroless/python3-debian11
COPY --from=builder /app /app
```

### 4. Never Store Secrets in Images

- Use environment variables or secrets managers
- Never embed credentials in Dockerfiles
- Use `.dockerignore` to exclude sensitive files

---

## Troubleshooting

### ECR Login Fails

```bash
# Check AWS credentials
aws sts get-caller-identity

# Ensure ECR permissions
aws ecr describe-repositories
```

### GCR Push Denied

```bash
# Re-authenticate
gcloud auth configure-docker

# Check permissions
gcloud projects get-iam-policy $GCP_PROJECT \
    --filter="bindings.members:serviceAccount:$SERVICE_ACCOUNT"
```

### Image Pull Rate Limits

For Docker Hub base images:
```yaml
# Use authenticated pulls or mirror images
services:
  docker:
    image: docker:dind
    environment:
      DOCKER_HUB_USERNAME: ${{ secrets.DOCKER_HUB_USERNAME }}
      DOCKER_HUB_TOKEN: ${{ secrets.DOCKER_HUB_TOKEN }}
```

### Build Cache Issues

```bash
# Clear GitHub Actions cache
gh cache delete --all

# Or build without cache
docker build --no-cache -t myimage .
```

---

## Quick Reference

### ECR Commands

```bash
# List images
aws ecr describe-images --repository-name news-scraper/api

# Delete image
aws ecr batch-delete-image \
    --repository-name news-scraper/api \
    --image-ids imageTag=dev

# Get scan results
aws ecr describe-image-scan-findings \
    --repository-name news-scraper/api \
    --image-id imageTag=latest
```

### GCR/Artifact Registry Commands

```bash
# List images
gcloud artifacts docker images list us-central1-docker.pkg.dev/$GCP_PROJECT/news-scraper

# Delete image
gcloud artifacts docker images delete \
    us-central1-docker.pkg.dev/$GCP_PROJECT/news-scraper/api:dev

# View vulnerabilities
gcloud artifacts docker images describe \
    us-central1-docker.pkg.dev/$GCP_PROJECT/news-scraper/api:latest \
    --show-package-vulnerability
```

---

*Last Updated: January 2026*
