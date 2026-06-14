_registry: dict[str, callable] = {}


def command(*names):
    def decorator(func):
        for name in names:
            _registry[name.lower()] = func
        return func
    return decorator


def get_handler(cmd: str):
    return _registry.get(cmd.lower())


def list_commands() -> list[str]:
    return list(_registry.keys())
