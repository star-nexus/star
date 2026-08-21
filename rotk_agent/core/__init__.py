"""Model- and mode-agnostic agent core.

Kept deliberately free of eager re-exports: `core.agent` needs the adapter and
mode packages, and those need `core`, so importing them from here would create a
cycle. Import the submodule you need, e.g. `from rotk_agent.core.agent import
RoTKChatAgent`.
"""
