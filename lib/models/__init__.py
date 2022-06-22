"""The module with models for the :class:`AdBotClient`."""

from typing import Final, Tuple

from ._mixins import Timestamped
from .bots.chat_model import ChatDeactivatedCause, ChatModel
from .bots.client_model import ClientModel
from .bots.reply_model import ReplyModel
from .bots.sent_ad_model import SentAdModel
from .clients.ad_model import AdModel
from .clients.bot_model import BotModel
from .clients.user_model import UserModel, UserRole
from .misc.category_model import CategoryModel
from .misc.input_message_model import InputMessageModel
from .misc.input_model import InputModel
from .misc.settings_model import SettingsModel
from .misc.subscription_model import SubscriptionModel
from .sessions.peer_model import PeerModel
from .sessions.session_model import SessionModel

__all__: Final[Tuple[str, ...]] = (
    'Timestamped',
    'AdModel',
    'InputModel',
    'BotModel',
    'PeerModel',
    'ChatDeactivatedCause',
    'ChatModel',
    'ClientModel',
    'SentAdModel',
    'SessionModel',
    'InputMessageModel',
    'UserModel',
    'UserRole',
    'ReplyModel',
    'CategoryModel',
    'SettingsModel',
    'SubscriptionModel',
)
