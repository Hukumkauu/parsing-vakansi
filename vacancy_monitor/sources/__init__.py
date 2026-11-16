from .hh import HHSource
from .superjob import SuperJobSource
from .trudvsem import TrudvsemSource

SOURCES = {
    "hh": HHSource,
    "trudvsem": TrudvsemSource,
    "superjob": SuperJobSource,
}


def build_sources(names, user_agent, hh_details=0):
    result = []
    for name in names:
        cls = SOURCES.get(name)
        if cls is None:
            raise ValueError(f"Неизвестный источник: {name}. Доступны: {', '.join(SOURCES)}")
        if cls is HHSource:
            result.append(cls(user_agent, details=hh_details))
        else:
            result.append(cls(user_agent))
    return result
