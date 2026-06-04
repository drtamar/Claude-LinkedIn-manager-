from jinja2 import Environment, BaseLoader, StrictUndefined


_env = Environment(loader=BaseLoader(), undefined=StrictUndefined)


def render(template_str: str, variables: dict) -> str:
    template = _env.from_string(template_str)
    return template.render(**variables)
