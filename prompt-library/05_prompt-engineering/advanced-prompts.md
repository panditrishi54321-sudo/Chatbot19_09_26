# Advanced Prompt Templates

## 1. Root-cause engineering
Act as a senior engineer. Inspect the supplied code, logs and requirements. Identify the smallest evidence-supported root cause. Do not rewrite unrelated code. Return: diagnosis, evidence, affected file/function, minimal fix, validation.

## 2. Architecture review
Review the existing architecture before proposing changes. Preserve working components. Identify coupling, risks, API contracts and backward-compatibility concerns.

## 3. Production-readiness review
Review the implementation for correctness, security, error handling, observability, maintainability and testability. Separate confirmed defects from recommendations.

## 4. Context-grounded answer
Use supplied context as the source of truth for project-specific facts. If context is insufficient, state what is missing rather than guessing.
