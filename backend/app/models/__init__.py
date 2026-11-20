"""ORM models.

Importing them here registers every table on ``Base.metadata`` and makes the string
references in ``relationship("Case")`` / ``relationship("User")`` resolvable no matter
which module is imported first.
"""

from app.models import case, user, token_blacklist  # noqa: F401