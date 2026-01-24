"""App entrypoint: wires UI and Core modules together."""

from nicegui import ui

from can_log_analyzer.ui.app_ui import create_ui


def main() -> None:
    create_ui()
    ui.run(title='CAN Log Analyzer', port=8080, reload=True)


if __name__ in {"__main__", "__mp_main__"}:
    main()
