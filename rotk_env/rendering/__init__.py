"""ENV renderer registration. No renderer is imported before it is selected."""

from importlib import import_module

_FACTORIES = {
    'pygame': ('rotk_env.rendering.pygame_adapter', 'PygameRenderer'),
    'none': ('rotk_env.rendering.adapters', 'ProjectionRenderer'),
    'web': ('rotk_env.rendering.adapters', 'WebRenderer'),
}


def register_renderer(name, factory):
    if not isinstance(name, str) or not name or name in _FACTORIES or not callable(factory):
        raise ValueError('renderer requires a unique name and a callable factory')
    _FACTORIES[name] = factory


def create_renderer(name, **context):
    try:
        factory = _FACTORIES[name]
    except KeyError:
        raise ValueError(f'Unknown renderer: {name}') from None
    if isinstance(factory, tuple):
        factory = getattr(import_module(factory[0]), factory[1])
    return factory(**context)
