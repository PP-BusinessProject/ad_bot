"""The module with :class:`AdBotClient` handlers."""

from enum import Enum
from typing import Final

from .bots import Bots
from .clients import Clients
from .misc import Misc
from .service import Service


class Messages(Bots, Clients, Misc, Service):
    pass


SEPARATOR: Final[str] = ''


class Commands(object):
    class PAGE(str, Enum):
        """The commands for working with pages."""

        _SELF: Final[str] = SEPARATOR.join(('P',))
        INFO: Final[str] = SEPARATOR.join((_SELF, 'I'))
        ERROR_LEFT: Final[str] = SEPARATOR.join((_SELF, 'E', 'L'))
        ERROR_RIGHT: Final[str] = SEPARATOR.join((_SELF, 'E', 'R'))

    class INPUT(str, Enum):
        """The commands to use when awaiting user inputs."""

        _SELF: Final[str] = SEPARATOR.join(('I',))
        CANCEL: Final[str] = SEPARATOR.join((_SELF, 'C'))

    class SERVICE(str, Enum):
        """The service commands."""

        _SELF: Final[str] = SEPARATOR.join(('_',))
        HIDE: Final[str] = SEPARATOR.join((_SELF, 'H'))
        APPROVE: Final[str] = SEPARATOR.join((_SELF, 'A'))
        DENY: Final[str] = SEPARATOR.join((_SELF, 'D'))

    class HELP(str, Enum):
        """The commands for showing help."""

        _SELF: Final[str] = SEPARATOR.join(('H',))
        ANSWER: Final[str] = SEPARATOR.join((_SELF, 'A'))
        CANCEL: Final[str] = SEPARATOR.join((_SELF, 'C'))

    class SUBSCRIPTION(str, Enum):
        """The commands for using subscripiton."""

        _SELF: Final[str] = SEPARATOR.join(('SU',))
        VIEW: Final[str] = SEPARATOR.join((_SELF, 'V'))
        APPLY: Final[str] = SEPARATOR.join((_SELF, 'A'))
        DENY: Final[str] = SEPARATOR.join((_SELF, 'D'))
        DENY_NO_REASON: Final[str] = SEPARATOR.join((DENY, 'N', 'R'))
        PICK: Final[str] = SEPARATOR.join((_SELF, 'P'))

    class BOT(str, Enum):
        """The commands to work with bots."""

        _SELF: Final[str] = SEPARATOR.join(('B',))
        LIST: Final[str] = SEPARATOR.join((_SELF, 'L'))
        PAGE: Final[str] = SEPARATOR.join((_SELF, 'P'))
        AUTHORIZE: Final[str] = SEPARATOR.join((_SELF, 'A'))
        BAN: Final[str] = SEPARATOR.join((_SELF, 'B'))
        ROLE: Final[str] = SEPARATOR.join((_SELF, 'R'))
        DELETE: Final[str] = SEPARATOR.join((_SELF, 'D'))
        DELETE_CONFIRM: Final[str] = SEPARATOR.join((DELETE, 'C'))

    class SETTINGS(str, Enum):
        """The commands to change bot settings."""

        _SELF: Final[str] = SEPARATOR.join(('B', 'S'))
        PAGE: Final[str] = SEPARATOR.join((_SELF, 'P'))
        APPLY: Final[str] = SEPARATOR.join((_SELF, 'A'))
        REFRESH: Final[str] = SEPARATOR.join((_SELF, 'R'))
        DOWNLOAD: Final[str] = SEPARATOR.join((_SELF, 'G'))

        FIRST_NAME: Final[str] = SEPARATOR.join((_SELF, 'F', 'N'))
        LAST_NAME: Final[str] = SEPARATOR.join((_SELF, 'L', 'N'))
        ABOUT: Final[str] = SEPARATOR.join((_SELF, 'AB'))
        USERNAME: Final[str] = SEPARATOR.join((_SELF, 'U'))
        REPLY: Final[str] = SEPARATOR.join((_SELF, 'REP'))
        REPLY_VIEW: Final[str] = SEPARATOR.join((REPLY, 'V'))
        CONTACT: Final[str] = SEPARATOR.join((_SELF, 'C'))
        AVATAR: Final[str] = SEPARATOR.join((_SELF, 'AV'))

    class SETTINGS_DELETE(str, Enum):
        """The commands to delete bot settings."""

        _SELF: Final[str] = SEPARATOR.join(('B', 'S', 'D'))
        FIRST_NAME: Final[str] = SEPARATOR.join((_SELF, 'F', 'N'))
        FIRST_NAME_CONFIRM: Final[str] = SEPARATOR.join((FIRST_NAME, 'C'))
        LAST_NAME: Final[str] = SEPARATOR.join((_SELF, 'L', 'N'))
        LAST_NAME_CONFIRM: Final[str] = SEPARATOR.join((LAST_NAME, 'C'))
        ABOUT: Final[str] = SEPARATOR.join((_SELF, 'A'))
        ABOUT_CONFIRM: Final[str] = SEPARATOR.join((ABOUT, 'C'))
        USERNAME: Final[str] = SEPARATOR.join((_SELF, 'U'))
        USERNAME_CONFIRM: Final[str] = SEPARATOR.join((USERNAME, 'C'))
        REPLY: Final[str] = SEPARATOR.join((_SELF, 'R'))
        REPLY_CONFIRM: Final[str] = SEPARATOR.join((REPLY, 'C'))
        CONTACT: Final[str] = SEPARATOR.join((_SELF, 'C'))
        CONTACT_CONFIRM: Final[str] = SEPARATOR.join((CONTACT, 'C'))
        AVATAR: Final[str] = SEPARATOR.join((_SELF, 'A'))
        AVATAR_CONFIRM: Final[str] = SEPARATOR.join((AVATAR, 'C'))

    class AD(str, Enum):
        """The commands to work with ads."""

        _SELF: Final[str] = SEPARATOR.join(('AD',))
        PAGE: Final[str] = SEPARATOR.join((_SELF, 'P'))
        VIEW: Final[str] = SEPARATOR.join((_SELF, 'V'))
        CATEGORY_DELETE: Final[str] = SEPARATOR.join((_SELF, 'CD'))
        CATEGORY_PICK: Final[str] = SEPARATOR.join((_SELF, 'CP'))
        JOURNAL: Final[str] = SEPARATOR.join((_SELF, 'J'))
        ACTIVE: Final[str] = SEPARATOR.join((_SELF, 'AC'))
        BAN: Final[str] = SEPARATOR.join((_SELF, 'B'))
        DELETE: Final[str] = SEPARATOR.join((_SELF, 'D'))
        DELETE_CONFIRM: Final[str] = SEPARATOR.join((DELETE, 'C'))

    class SENDER_CHAT(str, Enum):
        """The commands to work with sender chats."""

        _SELF: Final[str] = SEPARATOR.join(('SE', 'C'))
        LIST: Final[str] = SEPARATOR.join((_SELF, 'L'))
        PAGE: Final[str] = SEPARATOR.join((_SELF, 'P'))
        REFRESH: Final[str] = SEPARATOR.join((_SELF, 'R'))
        ACTIVATE: Final[str] = SEPARATOR.join((_SELF, 'A'))
        PERIOD_CHANGE: Final[str] = SEPARATOR.join((_SELF, 'P', 'C'))
        PERIOD_RESET: Final[str] = SEPARATOR.join((_SELF, 'P', 'R'))
        CATEGORY: Final[str] = SEPARATOR.join((_SELF, 'C'))
        REMOVE_CATEGORY: Final[str] = SEPARATOR.join((CATEGORY, 'R'))

    class SENDER_CLIENT(str, Enum):
        """The commands to work with sender clients."""

        _SELF: Final[str] = SEPARATOR.join(('C',))
        LIST: Final[str] = SEPARATOR.join((_SELF, 'L'))
        PAGE: Final[str] = SEPARATOR.join((_SELF, 'P'))
        REFRESH: Final[str] = SEPARATOR.join((_SELF, 'R'))
        ACTIVE: Final[str] = SEPARATOR.join((_SELF, 'A'))
        WARMUP: Final[str] = SEPARATOR.join((_SELF, 'W'))
        WARMUP_STATUS: Final[str] = SEPARATOR.join((_SELF, 'W', 'S'))
        DELETE: Final[str] = SEPARATOR.join((_SELF, 'D'))

        AUTH_SEND_SMS: Final[str] = SEPARATOR.join((_SELF, 'A', 'S'))
        AUTH_RECOVER_PASSWORD: Final[str] = SEPARATOR.join((_SELF, 'A', 'R'))
        AUTH_SKIP_LAST_NAME: Final[str] = SEPARATOR.join((_SELF, 'A', 'L'))
        AUTH_REGISTER_APPROVE: Final[str] = SEPARATOR.join(
            (_SELF, 'A', 'R', 'A')
        )
        AUTH_REGISTER_RETRY: Final[str] = SEPARATOR.join(
            (_SELF, 'A', 'R', 'R')
        )
