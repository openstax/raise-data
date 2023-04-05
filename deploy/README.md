# RAISE data deployment

## Overview

The code in this repo is deployed using Kubernetes. The deployment is automated via [CodePipeline](https://docs.aws.amazon.com/codepipeline). This directory includes all deployment related configuration files used for the application, with the exception of the AWS infrastructure resource definitions which live with the rest of the K12 IaC code. The subdirectories include:

* `buildspec/` - [CodeBuild](https://docs.aws.amazon.com/codebuild) buildspec files used in pipeline stages
* `chart/` - A Helm chart used to deploy to Kubernetes
* `k8s/` - Kubernetes configurations for deployed resources

The pipeline is configured to automatically update when PRs are merged to `main`.

## References

* [Build specification reference for CodeBuild](https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html)
* [Kubernetes API](https://kubernetes.io/docs/reference/kubernetes-api/)
