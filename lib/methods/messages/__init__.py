from .answer_edit_send import AnswerEditSend
from .forward_messages import ForwardMessages
from .send_or_edit import SendOrEdit


class Messages(AnswerEditSend, ForwardMessages, SendOrEdit):
    pass
