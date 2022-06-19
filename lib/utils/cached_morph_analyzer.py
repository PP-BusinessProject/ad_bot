"""The module to work with `MorphAnalyzer`."""

from abc import ABC
from datetime import timedelta
from decimal import Decimal
from typing import ClassVar, Type, Union

from pymorphy2.analyzer import MorphAnalyzer, Parse
from pymorphy2.tagset import OpencorporaTag
from typing_extensions import Self


class CachedMorphAnalyzer(ABC):
    """The morph analyzers that caches it's morphs."""

    _analyzer: ClassVar[MorphAnalyzer] = MorphAnalyzer()
    _morphs: ClassVar[dict[str, Parse]] = {}

    FRACTIONS: ClassVar[tuple[str, ...]] = (
        *('милли', 'микро', 'нано', 'пико'),
        *('фемто', 'атто', 'зепто', 'иокто'),
    )

    @classmethod
    def inflect(
        cls: Type[Self],
        /,
        *words: str,
        sep: str = ' ',
        case: str = '',
        time: str = '',
        person: int = 0,
    ) -> str:
        results: list[str] = []
        for word in map(lambda x: x.lower(), words):
            if word not in cls._morphs:
                cls._morphs[word] = cls._analyzer.parse(word)[0]
            if cls._morphs[word].tag.POS in ('NOUN', 'ADJF', 'PRTF'):
                parse = cls._morphs[word]
                if case in OpencorporaTag.CASES:
                    parse = parse.inflect({case})
            else:
                parse = cls._morphs[word].inflect(
                    {
                        _
                        for _ in (
                            time
                            if time in OpencorporaTag.TENSES
                            else 'pres'
                            if cls._morphs[word].tag.POS in ('INFN', 'VERB')
                            else None,
                            case if case in OpencorporaTag.CASES else None,
                            f'{person}per'
                            if f'{person}per' in OpencorporaTag.PERSONS
                            else '3per'
                            if cls._morphs[word].tag.POS in ('INFN', 'VERB')
                            else None,
                        )
                        if _ is not None
                    }
                )
            results.append(parse.word)
        return sep.join(results)

    @classmethod
    def plural(
        cls: Type[Self],
        number: Union[int, float, Decimal],
        /,
        *words: str,
        sep: str = ' ',
        case: str = '',
        time: str = '',
        person: int = 0,
    ) -> str:
        """
        Make the ``words`` in a plural form.

        Args:
            number (``Union[int, float, Decimal]``):
                The number to make the `words` the plural form of.

            words (``tuple[str, ...]``):
                The words to align with `number`.

            sep (``str``, *optional*):
                The separator to join the aligned `words`.

            case (``str``, *optional*):
                The case to put the `words` in.
                    Must be one of `~pymorphy2.tagset.OpencorporaTag.CASES`.

            time (``str``, *optional*):
                The time to put the verb `words` in.
                    Must be one of `~pymorphy2.tagset.OpencorporaTag.TENSES`.

            person (``str``, *optional*):
                The person to put the verb `words` in.
                    Must be one of `~pymorphy2.tagset.OpencorporaTag.PERSONS`.

        Returns:
            The string of the joined `words` aligned with `number`.
                Also returns an empty string if no `words` are provided.
        """
        results: list[str] = []
        for word in map(lambda x: x.lower(), words):
            if word not in cls._morphs:
                cls._morphs[word] = cls._analyzer.parse(word)[0]
            if cls._morphs[word].tag.POS in ('NOUN', 'ADJF', 'PRTF'):
                parse = cls._morphs[word].make_agree_with_number(number)
                if case in OpencorporaTag.CASES:
                    parse = parse.inflect({parse.tag.number, case})
            else:
                parse = cls._morphs[word].inflect(
                    {
                        _
                        for _ in (
                            'sing' if number == 1 else 'plur',
                            time
                            if time in OpencorporaTag.TENSES
                            else 'pres'
                            if cls._morphs[word].tag.POS in ('INFN', 'VERB')
                            else None,
                            case if case in OpencorporaTag.CASES else None,
                            f'{person}per'
                            if f'{person}per' in OpencorporaTag.PERSONS
                            else '3per'
                            if cls._morphs[word].tag.POS in ('INFN', 'VERB')
                            else None,
                        )
                        if _ is not None
                    }
                )
            results.append(parse.word)
        return sep.join(results)

    @classmethod
    def timedelta(
        cls: Type[Self],
        val: Union[int, float, Decimal, timedelta],
        /,
        precision: int = 6,
        *,
        value_sep: str = ' ',
        sep: str = ' ',
        case: str = '',
        single_fraction: bool = False,
    ) -> str:
        """
        Turn the `timedelta` into a proper string.

        Args:
            value (``Union[AnyNumber, timedelta]``):
                The timedelta or number of seconds to convert.

            precision (``int``, *optional*):
                The precision for the fractional part of the
                `timedelta.total_seconds()`.

            value_sep (``str``, *optional*):
                The separator between each numeric category name and value.

            sep (``str``, *optional*):
                The separator between numeric categories.

            case (``str``, *optional*):
                The case to put the numeric categories in.
                    Must be one of `~pymorphy2.tagset.OpencorporaTag.CASES`.

            single_fraction (``bool``, *optional*):
                If the converted string should have just one or all available
                fractions.

        Returns:
            The string converted from `timedelta`.
                Also returns an empty string if
                `timedelta.total_seconds() == 0`.
        """
        precision = min(len(cls.FRACTIONS) * 3, abs(precision))
        if isinstance(seconds := abs(val), timedelta):
            seconds = seconds.total_seconds()
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        seconds, fraction = divmod(seconds, 1)
        period = -(-(len(f'{fraction:.{precision}f}'.rstrip('0')) - 2) // 3)
        fraction = int(round(fraction, precision) * 10 ** (period * 3))
        return sep.join(
            f'{amount}{value_sep}{cls.plural(amount, noun, case=case)}'
            for amount, noun in (
                (int(days), 'день'),
                (int(hours), 'час'),
                (int(minutes), 'минута'),
                (int(seconds), 'секунда'),
            )
            + (
                ((fraction, f'{cls.FRACTIONS[period - 1]}секунда'),)
                if single_fraction
                else tuple(
                    (
                        int(str(fraction)[period * 3 : period * 3 + 3]),
                        f'{cls.FRACTIONS[period]}секунда',
                    )
                    for period in range(period)
                )
            )
            if amount > 0
        )
