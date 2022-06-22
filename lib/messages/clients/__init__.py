from .ad_message import AdMessage

from .bot_message import BotMessage
from .chat_message import ChatMessage
from .client_message import ClientMessage
from .settings_message import SettingsMessage
from .start_message import StartMessage


class Clients(
    AdMessage,
    BotMessage,
    ChatMessage,
    ClientMessage,
    SettingsMessage,
    StartMessage,
):
    pass
