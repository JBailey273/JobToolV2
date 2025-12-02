"""Context processors used across templates."""

from django.core.exceptions import ObjectDoesNotExist
from django.db.utils import OperationalError, ProgrammingError

from .models import GlobalSettings


def global_settings(request):
    """Provide global settings without breaking if the DB is unavailable.

    During initial setup or when migrations have not yet been applied the
    ``tracker_globalsettings`` table may not exist. Previously this raised
    an ``OperationalError`` which in turn caused a 500 error whenever a
    template tried to access the login page. By gracefully handling these
    database errors we can still render pages such as the login page and the
    rest of the site will work once migrations are applied.
    """

    try:
        settings_obj = GlobalSettings.objects.first()
    except (OperationalError, ProgrammingError):
        settings_obj = None

    return {"global_settings": settings_obj}


def contractor(request):
    """Provide the logged-in contractor for templates.

    Including this context processor ensures templates such as the dashboard
    base layout can always access ``contractor`` without each view needing to
    supply it explicitly.
    """

    user = getattr(request, "user", None)
    contract = None

    if getattr(user, "is_authenticated", False):
        try:
            contract = user.contractor
        except (OperationalError, ProgrammingError, ObjectDoesNotExist):
            contract = None

    return {"contractor": contract}
