"""Template renderer — Jinja2 sandbox rendering for SageMath code templates."""

import jinja2
import jinja2.sandbox


def render_template(sage_template: str, values: dict) -> str:
    """Render a Jinja2 template string with *values* using the sandboxed env.

    * Template syntax uses ``{{ ...|sage_literal }}`` for safe value insertion.
    * ``SandboxedEnvironment`` blocks dangerous attribute access (``__class__``,
      ``__mro__``, ``__subclasses__``, etc.).
    * ``StrictUndefined`` raises ``jinja2.UndefinedError`` (converted to
      ``ValueError``) for missing keys.
    * Extra keys in *values* that are not referenced by the template are silently
      ignored.

    Returns the rendered code string (execution is handled separately by
    :func:`src.sandbox.executor.run_sandboxed`).
    """
    env = jinja2.sandbox.SandboxedEnvironment(
        undefined=jinja2.StrictUndefined,
    )
    env.filters["sage_literal"] = repr

    try:
        return env.from_string(sage_template).render(**values)
    except jinja2.UndefinedError as exc:
        raise ValueError(str(exc)) from exc
    except jinja2.security.SecurityError as exc:
        raise RuntimeError(f"template blocked by sandbox: {exc}") from exc