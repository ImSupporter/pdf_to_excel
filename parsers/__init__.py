# parsers/__init__.py
from .samsung import SamsungParser
from .mirae_asset import MiraeAssetParser
from .citi import CitiParser

PARSERS: list = [SamsungParser, MiraeAssetParser, CitiParser]
