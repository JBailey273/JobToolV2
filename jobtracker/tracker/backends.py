from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.utils import OperationalError, ProgrammingError


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get('email')
        try:
            user = UserModel.objects.get(email=username)
        except (UserModel.DoesNotExist, OperationalError, ProgrammingError):
            return None
        else:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
