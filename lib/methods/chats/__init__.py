from .check_chats import CheckChats
from .get_channel_participants import GetChannelParticipants

from.get_peer_dialogs import GetPeerDialogs
from .iter_channel_participants import IterChannelParticipants
from .iter_dialogs import IterDialogs


class Chats(CheckChats,GetChannelParticipants,GetPeerDialogs,IterChannelParticipants,IterDialogs):
    pass
