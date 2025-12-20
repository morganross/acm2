"""
FPF-specific error classes.
"""


class FpfError(Exception):
    """Base exception for FPF adapter errors."""
    pass


class FpfExecutionError(FpfError):
    """Raised when FPF execution fails."""
    pass


class FpfTimeoutError(FpfError):
    """Raised when FPF execution times out."""
    pass


class FpfConfigError(FpfError):
    """Raised when FPF configuration is invalid."""
    pass