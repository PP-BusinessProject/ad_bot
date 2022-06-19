"""The module with custom Pyrogram methods."""

from .answer_edit_send import AnswerEditSend
from .apply_profile_settings import ApplyProfileSettings
from .check_chats import CheckChats
from .connect import Connect
from .disconnect import Disconnect
from .fetch_peers import FetchPeers
from .forward_messages import ForwardMessages
from .get_channel_participants import GetChannelParticipants
from .get_folder_by_title import GetFolderByTitle
from .get_folders import GetFolders
from .get_peer_dialogs import GetPeerDialogs
from .get_profile_settings import GetProfileSettings
from .initialize import Initialize
from .initialize_user_service import InitializeUserService
from .iter_channel_participants import IterChannelParticipants
from .iter_dialogs import IterDialogs
from .iter_profile_photos import IterProfilePhotos
from .resolve_peer import ResolvePeer
from .send import Send
from .send_code import SendCode
from .send_or_edit import SendOrEdit
from .set_privacy import SetPrivacy
from .sign_in_bot import SignInBot
from .terminate import Terminate
from .update_folder import UpdateFolder
from .validate import Validate


class Methods(
    AnswerEditSend,
    ApplyProfileSettings,
    CheckChats,
    Connect,
    Disconnect,
    FetchPeers,
    ForwardMessages,
    GetChannelParticipants,
    GetFolderByTitle,
    GetFolders,
    GetPeerDialogs,
    GetProfileSettings,
    Initialize,
    InitializeUserService,
    IterChannelParticipants,
    IterDialogs,
    IterProfilePhotos,
    ResolvePeer,
    Send,
    SendCode,
    SendOrEdit,
    SetPrivacy,
    SignInBot,
    Terminate,
    UpdateFolder,
    Validate,
):
    pass
