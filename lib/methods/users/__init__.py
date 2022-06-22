from .apply_profile_settings import ApplyProfileSettings
from .get_profile_settings import GetProfileSettings
from .initialize_user_service import InitializeUserService


class Users(
    ApplyProfileSettings,
    GetProfileSettings,
    InitializeUserService,
):
    pass
