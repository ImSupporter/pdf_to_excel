# parsers/__init__.py
from .samsung import SamsungParser
from .mirae_asset import MiraeAssetParser

PARSERS: list = [SamsungParser, MiraeAssetParser]
