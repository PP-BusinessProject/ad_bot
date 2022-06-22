from .connect import Connect
from .disconnect import Disconnect
from .initialize import Initialize
from .terminate import Terminate


class Init(Connect, Disconnect, Initialize, Terminate):
    pass
