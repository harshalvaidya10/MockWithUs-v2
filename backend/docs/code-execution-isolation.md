# Code Execution Isolation Strategy

This project runs candidate code through a dedicated `executor` service, not inside the main FastAPI API container.

## Threat model

Candidate code is untrusted and can attempt to:
- consume excessive CPU/memory/processes
- access environment secrets
- write to filesystem locations outside temporary workspace
- reach network targets

## Isolation controls

The default Docker Compose setup applies:
- Separate executor container (`backend/Dockerfile.executor`)
- Non-root runtime user (`UID/GID 10001`)
- Read-only root filesystem for executor
- `tmpfs` scratch space at `/tmp`
- Dropped Linux capabilities (`cap_drop: [ALL]`)
- `no-new-privileges` security option
- Internal-only Docker network for executor (`exec_net` with `internal: true`)
- Container-level limits (`pids_limit`, `mem_limit`, `cpus`)
- Process-level limits in executor (`RLIMIT_AS`, `RLIMIT_CPU`, `RLIMIT_NPROC`, `RLIMIT_NOFILE`, `RLIMIT_FSIZE`)
- Sanitized child process environment (`PATH`, locale, `HOME=/tmp`) with inherited secrets removed

## Service architecture

- API container sets `CODE_EXECUTION_MODE=remote` and calls the executor over authenticated HTTP (`X-Executor-Token`).
- Executor exposes only an internal endpoint (`/execute-once`) and optional health endpoint (`/healthz`).
- Shared secret is configured via `CODE_EXECUTOR_SHARED_SECRET` and enforced fail-closed by default.
- `CODE_EXECUTOR_ALLOW_UNAUTHENTICATED=1` can be used only for local troubleshooting when no secret is configured.

## Production hardening notes

For production Kubernetes or VM deployments, add node-level MAC policies (AppArmor/SELinux) and a strict seccomp profile in the runtime platform policy layer.
