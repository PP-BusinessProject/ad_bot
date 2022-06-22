from .category_message import CategoryMessage
from .input_message import InputMessage
from .page_message import PageMessage


class Misc(CategoryMessage, InputMessage, PageMessage):
    pass
