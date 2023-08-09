import icecream
import sys
from enum import IntEnum, auto


class LoggingLevel(IntEnum):
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()


loggin_level = LoggingLevel.DEBUG


def icecream_factory(
    logging_class, at_exit=lambda: (), prefix="LivingPark-utils", context=False
):
    if logging_class < loggin_level:
        return lambda msg: ()

    def output_function(s):
        icecream.colorizedStderrPrint(s)
        at_exit()

    return icecream.IceCreamDebugger(
        prefix=f"{prefix}|{logging_class.name}|",
        outputFunction=output_function,
        includeContext=context,
    )


debug = icecream_factory(LoggingLevel.DEBUG, context=True)
info = icecream_factory(LoggingLevel.INFO)
warning = icecream_factory(LoggingLevel.WARNING)
error = icecream_factory(LoggingLevel.ERROR, at_exit=lambda: sys.exit(1))
