from .send_code import SendCode
from .set_privacy import SetPrivacy
from .sign_in_bot import SignInBot
from .validate import Validate


class Auth(SendCode, SetPrivacy, SignInBot, Validate):
    pass
