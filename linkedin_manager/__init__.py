"""Claude-powered LinkedIn manager.

A toolkit that uses the Anthropic Claude API to help draft LinkedIn posts,
generate engagement (comments, replies, connection notes), optimize a
profile, and produce a polished CV — with an optional adapter for posting
to LinkedIn.
"""

from .config import Config

__version__ = "0.1.0"

__all__ = ["Config", "__version__"]
