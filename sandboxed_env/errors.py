class SandboxError(Exception):
    """Base sandbox error with optional location."""
    def __init__(self, message: str, *, lineno: int | None = None, col: int | None = None):
        super().__init__(message)
        self.lineno = lineno
        self.col = col

class StepLimitError(SandboxError):
    """Raised when instruction/step budget exceeded."""

class CapabilityBudgetError(SandboxError):
    """Raised when a capability exceeds its budget."""
