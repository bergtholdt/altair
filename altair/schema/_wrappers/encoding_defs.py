# This file auto-generated by `generate_schema_interface.py`.
# Do not modify this file directly.

from .channelwithlegend import ChannelWithLegend
from .field import Field
from .orderchannel import OrderChannel
from .positionchannel import PositionChannel


class Color(ChannelWithLegend):
    channel_name = 'color'


class Column(PositionChannel):
    channel_name = 'column'


class Detail(Field):
    channel_name = 'detail'


class Label(Field):
    channel_name = 'label'


class Order(OrderChannel):
    channel_name = 'order'


class Path(OrderChannel):
    channel_name = 'path'


class Row(PositionChannel):
    channel_name = 'row'


class Shape(ChannelWithLegend):
    channel_name = 'shape'


class Size(ChannelWithLegend):
    channel_name = 'size'


class Text(Field):
    channel_name = 'text'


class X(PositionChannel):
    channel_name = 'x'


class Y(PositionChannel):
    channel_name = 'y'


CHANNEL_CLASSES = {
    'color': Color,
    'column': Column,
    'detail': Detail,
    'label': Label,
    'order': Order,
    'path': Path,
    'row': Row,
    'shape': Shape,
    'size': Size,
    'text': Text,
    'x': X,
    'y': Y,
}

CHANNEL_NAMES = list(CHANNEL_CLASSES.keys())