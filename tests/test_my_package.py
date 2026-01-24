import pytest
from pathlib import Path
from unittest.mock import MagicMock
from can_log_analyzer.core.analyzer import AnalyzerCore
from can_log_analyzer.ui.app_ui import CANLogAnalyzerUI
import tempfile


class TestAnalyzerCore:
    """Tests for AnalyzerCore functionality."""

    def test_init_creates_empty_state(self):
        """Test that AnalyzerCore initializes with empty state."""
        core = AnalyzerCore()
        assert core.database is None
        assert core.log_file_path is None
        assert core.db_file_path is None
        assert len(core.available_channels) == 0
        assert len(core.available_messages) == 0
        assert core.time_min is None
        assert core.time_max is None

    def test_load_database_with_invalid_format(self):
        """Test load_database raises error for unsupported format."""
        core = AnalyzerCore()
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            with pytest.raises(ValueError, match="Unsupported database file format"):
                core.load_database(tmp_path)
        finally:
            tmp_path.unlink()

    def test_get_available_channels_returns_sorted_list(self):
        """Test get_available_channels returns sorted channel list."""
        core = AnalyzerCore()
        core.available_channels = {2, 0, 1}
        channels = core.get_available_channels()
        assert channels == [0, 1, 2]

    def test_get_available_channels_empty(self):
        """Test get_available_channels returns empty list when no channels."""
        core = AnalyzerCore()
        channels = core.get_available_channels()
        assert channels == []

    def test_get_matching_messages_without_database(self):
        """Test get_matching_messages returns empty dict without database."""
        core = AnalyzerCore()
        result = core.get_matching_messages(0)
        assert result == {}

    def test_get_signals_for_messages_without_database(self):
        """Test get_signals_for_messages returns empty dict without database."""
        core = AnalyzerCore()
        result = core.get_signals_for_messages([0x123])
        assert result == {}

    def test_decode_without_log_file_raises_error(self):
        """Test decode raises RuntimeError when log file not loaded."""
        core = AnalyzerCore()
        core.database = MagicMock()
        with pytest.raises(RuntimeError, match="Database and log file must be loaded"):
            core.decode(0, [0x123], ["signal1"])

    def test_decode_without_database_raises_error(self):
        """Test decode raises RuntimeError when database not loaded."""
        core = AnalyzerCore()
        core.log_file_path = Path("/tmp/test.asc")
        with pytest.raises(RuntimeError, match="Database and log file must be loaded"):
            core.decode(0, [0x123], ["signal1"])

    def test_scan_log_file_with_no_path(self):
        """Test scan_log_file does nothing when no path is set."""
        core = AnalyzerCore()
        core.scan_log_file()
        assert len(core.available_channels) == 0
        assert core.time_min is None
        assert core.time_max is None


class TestCANLogAnalyzerUI:
    """Tests for CANLogAnalyzerUI functionality."""

    def test_ui_init_creates_ui_state(self):
        """Test that CANLogAnalyzerUI initializes with correct state."""
        ui = CANLogAnalyzerUI()
        assert ui.core is not None
        assert isinstance(ui.core, AnalyzerCore)
        assert ui.selected_channel is None
        assert ui.selected_messages == []
        assert ui.selected_signals == []
        assert ui.decoded_data == {}
        assert ui.theme == 'dark'

    def test_ui_has_palette_colors(self):
        """Test that UI has dark and light palettes defined."""
        ui = CANLogAnalyzerUI()
        assert len(ui.palette_dark) == 10
        assert len(ui.palette_light) == 10
        assert isinstance(ui.palette_dark[0], str)
        assert isinstance(ui.palette_light[0], str)

    def test_get_theme_colors_dark(self):
        """Test get_theme_colors returns dark theme colors."""
        ui = CANLogAnalyzerUI()
        ui.theme = 'dark'
        colors = ui.get_theme_colors()
        assert colors['paper_bg'] == '#0d1117'
        assert colors['plot_bg'] == '#0d1117'
        assert colors['font'] == '#c9d1d9'
        assert colors['grid'] == '#30363d'

    def test_get_theme_colors_light(self):
        """Test get_theme_colors returns light theme colors."""
        ui = CANLogAnalyzerUI()
        ui.theme = 'light'
        colors = ui.get_theme_colors()
        assert colors['paper_bg'] == '#ffffff'
        assert colors['plot_bg'] == '#ffffff'
        assert colors['font'] == '#24292f'
        assert colors['grid'] == '#d0d7de'

    def test_show_error_updates_status_label(self):
        """Test show_error updates status label."""
        ui = CANLogAnalyzerUI()
        mock_label = MagicMock()
        ui.status_label = mock_label
        ui.show_error("Test error")
        assert mock_label.text == "❌ Error: Test error"

    def test_show_success_updates_status_label(self):
        """Test show_success updates status label."""
        ui = CANLogAnalyzerUI()
        mock_label = MagicMock()
        ui.status_label = mock_label
        ui.show_success("Test success")
        assert mock_label.text == "✅ Test success"

    def test_show_info_updates_status_label(self):
        """Test show_info updates status label."""
        ui = CANLogAnalyzerUI()
        mock_label = MagicMock()
        ui.status_label = mock_label
        ui.show_info("Test info")
        assert mock_label.text == "ℹ️ Test info"

    def test_show_error_without_label(self):
        """Test show_error handles missing status label gracefully."""
        ui = CANLogAnalyzerUI()
        ui.status_label = None
        # Should not raise an error
        ui.show_error("Test error")

    def test_update_channel_selection_enables_select(self):
        """Test update_channel_selection enables channel select when channels available."""
        ui = CANLogAnalyzerUI()
        mock_select = MagicMock()
        ui.channel_select = mock_select
        ui.core.available_channels = {0, 1, 2}
        ui.update_channel_selection()
        mock_select.set_enabled.assert_called_with(True)

    def test_update_channel_selection_disables_select_when_empty(self):
        """Test update_channel_selection disables channel select when no channels."""
        ui = CANLogAnalyzerUI()
        mock_select = MagicMock()
        ui.channel_select = mock_select
        ui.core.available_channels = set()
        ui.update_channel_selection()
        mock_select.set_enabled.assert_called_with(False)

    def test_on_channel_selected_updates_selection(self):
        """Test on_channel_selected updates selected_channel."""
        ui = CANLogAnalyzerUI()
        ui.status_label = MagicMock()
        mock_event = MagicMock()
        mock_event.value = 2
        ui.on_channel_selected(mock_event)
        assert ui.selected_channel == 2

    def test_on_messages_selected_updates_selection(self):
        """Test on_messages_selected updates selected_messages."""
        ui = CANLogAnalyzerUI()
        ui.status_label = MagicMock()
        mock_event = MagicMock()
        mock_event.value = [0x123, 0x456]
        ui.on_messages_selected(mock_event)
        assert ui.selected_messages == [0x123, 0x456]

    def test_on_messages_selected_with_none_clears_selection(self):
        """Test on_messages_selected handles None value."""
        ui = CANLogAnalyzerUI()
        ui.status_label = MagicMock()
        mock_event = MagicMock()
        mock_event.value = None
        ui.on_messages_selected(mock_event)
        assert ui.selected_messages == []

    def test_on_signals_selected_updates_selection(self):
        """Test on_signals_selected updates selected_signals."""
        ui = CANLogAnalyzerUI()
        ui.status_label = MagicMock()
        mock_event = MagicMock()
        mock_event.value = ["signal1", "signal2"]
        ui.on_signals_selected(mock_event)
        assert ui.selected_signals == ["signal1", "signal2"]

    def test_update_signal_selection_clears_when_no_messages(self):
        """Test update_signal_selection clears signals when no messages selected."""
        ui = CANLogAnalyzerUI()
        mock_select = MagicMock()
        ui.signal_select = mock_select
        ui.selected_messages = []
        ui.update_signal_selection()
        mock_select.options = {}
        mock_select.set_enabled.assert_called_with(False)

    def test_update_message_selection_without_database(self):
        """Test update_message_selection without database doesn't raise error."""
        ui = CANLogAnalyzerUI()
        ui.selected_channel = 0
        ui.core.database = None
        # Should not raise an error
        ui.update_message_selection()

    def test_ui_max_points_default(self):
        """Test UI initializes with default max_points."""
        ui = CANLogAnalyzerUI()
        assert ui.max_points == 5000