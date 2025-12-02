from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpResponseServerError


class PendingMigrationMiddleware:
    """Surface pending migrations as a clear error message.

    After schema changes are deployed without running ``migrate`` the site would
    previously fail with a generic 500 error (e.g. missing column errors from
    the database). By checking for unapplied migrations when the server starts
    handling requests we can return a more actionable message that points to the
    root cause instead of an opaque server error.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._checked = False
        self._has_pending = False
        self._error = None

    def _check_migrations(self):
        """Detect unapplied migrations and cache the result.

        We re-run this when a pending state has been detected so that applying
        migrations while the server is running clears the error instead of
        permanently short-circuiting requests until the process restarts.
        """

        try:
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            self._has_pending = bool(plan)
            self._error = None
        except Exception as exc:  # pragma: no cover - defensive
            self._has_pending = False
            self._error = exc
        finally:
            self._checked = True

    def __call__(self, request):
        if not self._checked or self._has_pending or self._error:
            self._check_migrations()

        if self._has_pending or self._error:
            message = (
                "Database migrations are missing. Please run `python manage.py "
                "migrate` to update the schema."
            )
            if self._error:
                message += f"\nDetails: {self._error}"
            return HttpResponseServerError(message)

        return self.get_response(request)
