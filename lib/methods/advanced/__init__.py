from .fetch_peers import FetchPeers
from .invoke import Invoke
from .resolve_peer import ResolvePeer


class Advanced(FetchPeers, Invoke, ResolvePeer):
    pass
