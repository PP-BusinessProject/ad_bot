from .connect import Connect
from .disconnect import Disconnect
from .initialize import Initialize
from .start import Start
from .terminate import Terminate


class Init(Connect, Disconnect, Initialize, Start, Terminate):
    pass
