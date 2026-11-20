class JobbotError(Exception):
    """Base class for errors that should end a command with a clear message rather than a traceback."""


class BudgetExceeded(JobbotError):
    pass


class FixtureMissing(JobbotError):
    pass


class EmailBlocked(JobbotError):
    pass


class UsageError(JobbotError):
    pass
