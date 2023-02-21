"""The module with utils needed for working with `messages`."""

from datetime import datetime
from typing import TYPE_CHECKING, Union

from dateutil.tz.tz import tzlocal

from ...models.clients.ad_model import AdModel
from ...models.clients.bot_model import BotModel
from ...models.clients.user_model import UserModel, UserRole
from ...models.bots.sent_ad_model import SentAdModel

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


def subscription_text(user: UserModel, /) -> str:
    if not user.is_subscribed or not user.subscription_from:
        return '__Подписка не оформлена.__'
    subscription_end = user.subscription_from + user.subscription_period
    return (
        '__Подписка активна до:__ '
        if subscription_end > datetime.now(tzlocal())
        else '__Подписка просрочена с:__ '
    ) + subscription_end.astimezone().strftime(r'%Y-%m-%d %H:%M:%S')


def message_header(
    client: 'AdBotClient',
    model: Union[BotModel, AdModel, SentAdModel],
    /,
    from_user_id: int,
) -> str:
    """
    Return message header for specified `model`.

    Args:
        model (``Union[BotModel, AdModel]``):
            The model to return header for.

        from_user_id (``int``):
            The id of a user that requested header creation.

    Returns:
        Created message header for specified `model`.
    """

    def whose(user: UserModel, /) -> str:
        return '([{role}](tg://user?id={id}))'.format(
            id=user.id,
            role=client.morph.inflect(user.role.translation, case='gent'),
        )

    def confirmed(user: UserModel, /) -> str:
        nonlocal model
        confirmed = (
            f"Подтвержден{'о' if isinstance(model, AdModel) else ''}"
            if model.confirmed
            else 'Ожидает подтверждения'
        )
        if user.service_invite and (
            user.role >= UserRole.SUPPORT or user.id != from_user_id
        ):
            confirmed = f'[{confirmed}](%s)' % user.service_invite
        return ('**%s**' if model.confirmed else '__%s__') % confirmed

    if isinstance(model, SentAdModel):
        return '  '.join(
            _
            for _ in (
                f'**История объявления #{model.ad.message_id}**',
                f'**__([Бота #{model.ad.owner_bot.id}]'
                f'(t.me/+{model.ad.owner_bot.phone_number}))__**'
                if model.ad.owner_bot.phone_number is not None
                else f'**(Бота #{model.ad.owner_bot.id})**',
                whose(model.ad.owner_bot.owner)
                if model.ad.owner_bot.owner.id != from_user_id
                else None,
            )
            if _ is not None
        )

    elif isinstance(model, AdModel):
        return '  '.join(
            _
            for _ in (
                f'**Объявление #{model.message_id}**',
                f'**__([Бота #{model.owner_bot.id}]'
                f'(t.me/+{model.owner_bot.phone_number}))__**'
                if model.owner_bot.phone_number is not None
                else f'**(Бота #{model.owner_bot.id})**',
                whose(model.owner_bot.owner)
                if model.owner_bot.owner.id != from_user_id
                else None,
                confirmed(model.owner_bot.owner),
            )
            if _ is not None
        )

    elif isinstance(model, BotModel):
        return '  '.join(
            _
            for _ in (
                f'**__[Бот #{model.id}](t.me/+{model.phone_number})__**'
                if model.phone_number is not None
                else f'**Бот #{model.id}**',
                whose(model.owner) if model.owner.id != from_user_id else None,
                confirmed(model.owner),
            )
            if _ is not None
        )
