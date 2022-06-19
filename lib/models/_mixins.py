"""The module with the mixins for the mapped classes."""

from datetime import datetime

from sqlalchemy.orm.decl_api import declared_attr
from sqlalchemy.sql.sqltypes import DateTime
from sqlalchemy.sql.schema import Column
from typing_extensions import Self
from sqlalchemy.sql.functions import now


class Timestamped(object):
    """The mixin for setting timestamps for the mapped classes."""

    @declared_attr
    def created_at(self: Self, /) -> Column[datetime]:
        """Set the date and time when the instance was created."""
        return Column(
            'CreatedAt',
            DateTime(timezone=True),
            nullable=False,
            default=now(),
            key='created_at',
        )

    @declared_attr
    def updated_at(self: Self, /) -> Column[datetime]:
        """Set the date and time of the last time the instance was updated."""
        return Column(
            'UpdatedAt',
            DateTime(timezone=True),
            nullable=False,
            default=now(),
            onupdate=now(),
            key='updated_at',
        )
