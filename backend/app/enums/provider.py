from enum import Enum


class Provider(str, Enum):
    VEO = "veo"
    RUNWAY = "runway"
    KLING = "kling"