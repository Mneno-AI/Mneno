import io

from rich.console import Console

from mneno.cli import output


def test_success_uses_ascii_fallback_when_console_cannot_encode_symbol(monkeypatch) -> None:
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252")
    fallback_console = Console(file=stream, force_terminal=False, color_system=None)
    monkeypatch.setattr(output, "console", fallback_console)

    output.success("Memory added")
    stream.flush()
    rendered = buffer.getvalue().decode("cp1252")

    assert "[OK] Memory added" in rendered
    assert "✓" not in rendered
