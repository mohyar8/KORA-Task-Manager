"""Central append-only audit log of successful state changes.

Generic: it imports no business domain. Each domain declares its own `AuditAction`s (with an
explicit metadata allowlist) and records them through `audit.service.record` inside the same
transaction as the change.
"""
