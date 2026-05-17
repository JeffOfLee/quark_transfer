class QuarkTransferError(Exception):
    """Base exception for user-facing failures."""

    exit_code = 1


class ConfigError(QuarkTransferError):
    exit_code = 2


class AuthError(QuarkTransferError):
    exit_code = 3


class NotFoundError(QuarkTransferError):
    exit_code = 4


class DownloadError(QuarkTransferError):
    exit_code = 5

