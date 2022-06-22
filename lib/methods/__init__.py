from .advanced import Advanced
from .auth import Auth
from .chats import Chats
from .folders import Folders
from .init import Init
from .messages import Messages
from .users import Users


class Methods(Advanced, Auth, Chats, Folders, Init, Messages, Users):
    pass
