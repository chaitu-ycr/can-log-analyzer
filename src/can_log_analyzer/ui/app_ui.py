from pathlib import Path
from typing import Optional, Dict, List

import plotly.graph_objects as go
from nicegui import ui

from can_log_analyzer.core.analyzer import AnalyzerCore


class CANLogAnalyzerUI:
    def __init__(self) -> None:
        self.core = AnalyzerCore()

        # UI state
        self.selected_channel: Optional[int] = None
        self.selected_messages: List[int] = []
        self.selected_signals: List[str] = []
        self.decoded_data: Dict[str, Dict[str, List]] = {}
        self.time_start: Optional[float] = None
        self.time_end: Optional[float] = None
        self.max_points: int = 5000

        # UI components
        self.channel_select: Optional[ui.select] = None
        self.message_select: Optional[ui.select] = None
        self.signal_select: Optional[ui.select] = None
        self.plot_mode_select: Optional[ui.select] = None
        self.plot_container: Optional[ui.column] = None
        self.status_label: Optional[ui.label] = None
        self.time_start_input: Optional[ui.number] = None
        self.time_end_input: Optional[ui.number] = None
        self.max_points_input: Optional[ui.number] = None
        self.theme_toggle: Optional[ui.toggle] = None

        # Theme state and palettes
        self.theme: str = 'dark'  # 'light' or 'dark'
        self.palette_dark = [
            '#39d353', '#2f81f7', '#d29922', '#f85149', '#a371f7',
            '#58a6ff', '#ff7b72', '#3fb950', '#ffae33', '#ffa657'
        ]
        self.palette_light = [
            '#0969da', '#1a7f37', '#cf222e', '#9a6700', '#8250df',
            '#bf3989', '#0a3069', '#116329', '#b35900', '#622cbc'
        ]

    def get_theme_colors(self) -> Dict[str, str]:
        if self.theme == 'dark':
            return {
                'paper_bg': '#0d1117',
                'plot_bg': '#0d1117',
                'font': '#c9d1d9',
                'grid': '#30363d',
            }
        else:
            return {
                'paper_bg': '#ffffff',
                'plot_bg': '#ffffff',
                'font': '#24292f',
                'grid': '#d0d7de',
            }

    def on_theme_toggle(self, e) -> None:
        val = e.value
        self.theme = 'dark' if val == 'dark' or val is True else 'light'
        try:
            ui.run_javascript(f"document.documentElement.setAttribute('data-theme','{self.theme}')")
        except Exception:
            pass
        # Re-render plots with new theme if data exists
        if self.plot_container:
            self.plot_container.clear()
        if self.decoded_data and (self.plot_mode_select and self.plot_mode_select.value):
            mode = self.plot_mode_select.value
            if mode == 'separate':
                self.create_separate_plots()
            else:
                self.create_combined_plot()

    # ---------- Notifications ----------
    def show_error(self, message: str):
        ui.notify(message, type='negative', position='top')
        if self.status_label:
            self.status_label.text = f'❌ Error: {message}'
            self.status_label.classes('text-red-600')

    def show_success(self, message: str):
        ui.notify(message, type='positive', position='top')
        if self.status_label:
            self.status_label.text = f'✅ {message}'
            self.status_label.classes('text-green-600')

    def show_info(self, message: str):
        if self.status_label:
            self.status_label.text = f'ℹ️ {message}'
            self.status_label.classes('text-blue-600')

    # ---------- Upload Handlers ----------
    async def handle_database_upload(self, e):
        try:
            if not hasattr(e, 'file') or not e.file:
                self.show_error('No file provided in upload event')
                return
            file_obj = e.file
            file_name = getattr(file_obj, 'name', None)
            if not file_name:
                self.show_error('Unable to get filename from uploaded file')
                return
            ext = Path(file_name).suffix.lower()
            if ext not in ['.dbc', '.arxml']:
                self.show_error(f'Invalid database file: {file_name}. Please upload .dbc or .arxml file')
                return

            content_data = None
            if hasattr(file_obj, 'content'):
                content_obj = file_obj.content
                if hasattr(content_obj, 'read'):
                    read_result = content_obj.read()
                    if hasattr(read_result, '__await__'):
                        content_data = await read_result
                    else:
                        content_data = read_result
                else:
                    content_data = content_obj
            elif hasattr(file_obj, 'read'):
                read_result = file_obj.read()
                if hasattr(read_result, '__await__'):
                    content_data = await read_result
                else:
                    content_data = read_result
            if content_data is None:
                self.show_error('Failed to read uploaded database file')
                return

            import tempfile
            tmp_path = Path(tempfile.gettempdir()) / f"uploaded_db{ext}"
            # ensure bytes
            if isinstance(content_data, str):
                content_bytes = content_data.encode('utf-8')
            else:
                content_bytes = content_data
            with open(tmp_path, 'wb') as f:
                f.write(content_bytes)

            count = self.core.load_database(tmp_path)
            self.show_success(f'Loaded database {file_name} with {count} messages')
            # refresh channel selector (in case log is already loaded)
            self.update_channel_selection()
            # if a channel is already selected, refresh messages
            if self.selected_channel is not None:
                self.update_message_selection()
        except Exception as ex:
            self.show_error(f'Failed to load database: {str(ex)}')

    async def handle_log_upload(self, e):
        try:
            if not hasattr(e, 'file') or not e.file:
                self.show_error('No file provided in upload event')
                return
            file_obj = e.file
            file_name = getattr(file_obj, 'name', None)
            if not file_name:
                self.show_error('Unable to get filename from uploaded file')
                return
            ext = Path(file_name).suffix.lower()
            if ext not in ['.blf', '.asc']:
                self.show_error(f'Invalid log file: {file_name}. Please upload .blf or .asc file')
                return

            content_data = None
            if hasattr(file_obj, 'content'):
                content_obj = file_obj.content
                if hasattr(content_obj, 'read'):
                    read_result = content_obj.read()
                    if hasattr(read_result, '__await__'):
                        content_data = await read_result
                    else:
                        content_data = read_result
                else:
                    content_data = content_obj
            elif hasattr(file_obj, 'read'):
                read_result = file_obj.read()
                if hasattr(read_result, '__await__'):
                    content_data = await read_result
                else:
                    content_data = read_result
            if content_data is None:
                self.show_error('Failed to read uploaded log file')
                return

            import tempfile
            tmp_path = Path(tempfile.gettempdir()) / f"uploaded_log{ext}"
            if isinstance(content_data, str):
                content_bytes = content_data.encode('utf-8')
            else:
                content_bytes = content_data
            with open(tmp_path, 'wb') as f:
                f.write(content_bytes)

            channel_count = self.core.load_log(tmp_path)
            # reset selections tied to log contents
            self.selected_channel = None
            self.selected_messages = []
            self.selected_signals = []
            self.update_channel_selection()
            self.show_success(f'Loaded log {file_name} with {channel_count} channel(s)')
        except Exception as ex:
            self.show_error(f'Failed to load log file: {str(ex)}')

    def update_channel_selection(self):
        if self.channel_select:
            channels = self.core.get_available_channels()
            self.channel_select.options = channels
            self.channel_select.value = None
            self.channel_select.update()
            self.channel_select.set_enabled(bool(channels))

    def on_channel_selected(self, e):
        try:
            self.selected_channel = e.value
            self.show_info(f'Channel {self.selected_channel} selected')
            self.update_message_selection()
        except Exception as ex:
            self.show_error(f'Error selecting channel: {str(ex)}')

    def update_message_selection(self):
        try:
            if self.selected_channel is None or not self.core.database:
                return
            available_msg_dict = self.core.get_matching_messages(self.selected_channel)
            if self.message_select:
                self.message_select.options = available_msg_dict
                self.message_select.value = []
                self.message_select.update()
                self.message_select.set_enabled(bool(available_msg_dict))
                if available_msg_dict:
                    self.show_info(f'{len(available_msg_dict)} messages available for selection')
                else:
                    self.show_error('No matching messages found in database and log file')
        except Exception as ex:
            self.show_error(f'Error updating messages: {str(ex)}')

    def on_messages_selected(self, e):
        try:
            self.selected_messages = e.value if e.value else []
            self.show_info(f'{len(self.selected_messages)} message(s) selected')
            self.update_signal_selection()
        except Exception as ex:
            self.show_error(f'Error selecting messages: {str(ex)}')

    def update_signal_selection(self):
        try:
            if not self.selected_messages or not self.core.database:
                if self.signal_select:
                    self.signal_select.options = {}
                    self.signal_select.value = []
                    self.signal_select.update()
                    self.signal_select.set_enabled(False)
                return
            signal_dict = self.core.get_signals_for_messages(self.selected_messages)
            if self.signal_select:
                self.signal_select.options = signal_dict
                self.signal_select.value = []
                self.signal_select.update()
                self.signal_select.set_enabled(bool(signal_dict))
                if signal_dict:
                    self.show_info(f'{len(signal_dict)} signals available for selection')
        except Exception as ex:
            self.show_error(f'Error updating signals: {str(ex)}')

    def on_signals_selected(self, e):
        try:
            self.selected_signals = e.value if e.value else []
            self.show_info(f'{len(self.selected_signals)} signal(s) selected')
        except Exception as ex:
            self.show_error(f'Error selecting signals: {str(ex)}')

    # ---------- Plotting ----------
    def plot_signals(self):
        try:
            if self.plot_container:
                self.plot_container.clear()

            if not (self.core.log_file_path and self.core.database and self.selected_channel is not None 
                    and self.selected_messages and self.selected_signals):
                self.show_error('Please complete all selections before plotting')
                return

            # read time range and max_points
            start = self.time_start_input.value if self.time_start_input else None
            end = self.time_end_input.value if self.time_end_input else None
            if start is not None and end is not None and start > end:
                self.show_error('Start time must be <= end time')
                return
            mp = None
            if self.max_points_input and self.max_points_input.value:
                try:
                    mp = int(self.max_points_input.value)
                except Exception:
                    mp = None

            self.decoded_data = self.core.decode(
                self.selected_channel,
                self.selected_messages,
                self.selected_signals,
                time_range=(start, end),
                max_points=mp,
            )

            if not self.decoded_data or not any(self.decoded_data[k]['values'] for k in self.decoded_data):
                self.show_error('No data to plot')
                return

            plot_mode = self.plot_mode_select.value if self.plot_mode_select else 'separate'
            with self.plot_container:
                if plot_mode == 'separate':
                    self.create_separate_plots()
                else:
                    self.create_combined_plot()
        except Exception as ex:
            self.show_error(f'Failed to plot signals: {str(ex)}')

    def create_separate_plots(self):
        colors = self.get_theme_colors()
        palette = self.palette_dark if self.theme == 'dark' else self.palette_light
        for idx, (signal_key, data) in enumerate(self.decoded_data.items()):
            if not data['values']:
                continue
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=data['timestamps'],
                y=data['values'],
                mode='lines',
                name=signal_key,
                line=dict(width=2, color=palette[idx % len(palette)])
            ))
            fig.update_layout(
                title=signal_key,
                xaxis_title='Time (s)',
                yaxis_title=signal_key,
                height=300,
                margin=dict(l=50, r=20, t=40, b=40),
                showlegend=False,
                paper_bgcolor=colors['paper_bg'],
                plot_bgcolor=colors['plot_bg'],
                font=dict(size=12, color=colors['font'])
            )
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor=colors['grid'], zerolinecolor=colors['grid'])
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor=colors['grid'], zerolinecolor=colors['grid'])
            ui.plotly(fig).classes('w-full')

    def create_combined_plot(self):
        colors = self.get_theme_colors()
        palette = self.palette_dark if self.theme == 'dark' else self.palette_light
        fig = go.Figure()
        for idx, (signal_key, data) in enumerate(self.decoded_data.items()):
            if not data['values']:
                continue
            fig.add_trace(go.Scatter(
                x=data['timestamps'],
                y=data['values'],
                mode='lines',
                name=signal_key,
                line=dict(width=2, color=palette[idx % len(palette)])
            ))
            fig.update_layout(
                title='Combined Signal Plot',
                xaxis_title='Time (s)',
                yaxis_title='Signal Values',
                height=500,
                margin=dict(l=50, r=150, t=40, b=40),
                showlegend=True,
                legend=dict(x=1.02, y=1, xanchor='left', yanchor='top', font=dict(color=colors['font'])),
                paper_bgcolor=colors['paper_bg'],
                plot_bgcolor=colors['plot_bg'],
                font=dict(size=12, color=colors['font'])
            )
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor=colors['grid'], zerolinecolor=colors['grid'])
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor=colors['grid'], zerolinecolor=colors['grid'])
        ui.plotly(fig).classes('w-full')

    # ---------- Selections Reset ----------
    def clear_selections(self):
        try:
            self.selected_channel = None
            self.selected_messages = []
            self.selected_signals = []
            self.decoded_data = {}
            if self.channel_select:
                self.channel_select.value = None
                self.channel_select.update()
            if self.message_select:
                self.message_select.options = {}
                self.message_select.value = []
                self.message_select.update()
                self.message_select.set_enabled(False)
            if self.signal_select:
                self.signal_select.options = {}
                self.signal_select.value = []
                self.signal_select.update()
                self.signal_select.set_enabled(False)
            if self.plot_container:
                self.plot_container.clear()
            self.show_info('Selections cleared')
        except Exception as ex:
            self.show_error(f'Failed to clear selections: {str(ex)}')

    # ---------- Export ----------
    def _prepare_long_dataframe(self):
        try:
            import pandas as pd
        except Exception as ex:
            self.show_error('pandas not installed. Please install pandas to export.')
            return None
        rows = []
        for key, series in self.decoded_data.items():
            ts = series.get('timestamps', [])
            vs = series.get('values', [])
            for t, v in zip(ts, vs):
                rows.append({'signal': key, 'timestamp': t, 'value': v})
        if not rows:
            return None
        df = pd.DataFrame(rows)
        return df

    def export_csv(self):
        try:
            if not self.decoded_data:
                self.show_error('No decoded data to export')
                return
            df = self._prepare_long_dataframe()
            if df is None:
                self.show_error('No data to export')
                return
            import tempfile, time
            tmp = Path(tempfile.gettempdir()) / f"decoded_{int(time.time())}.csv"
            df.to_csv(tmp, index=False)
            ui.download(tmp)
            self.show_success(f'Exported CSV: {tmp.name}')
        except Exception as ex:
            self.show_error(f'CSV export failed: {str(ex)}')

    def export_parquet(self):
        try:
            if not self.decoded_data:
                self.show_error('No decoded data to export')
                return
            df = self._prepare_long_dataframe()
            if df is None:
                self.show_error('No data to export')
                return
            # Try writing with pyarrow (preferred)
            import tempfile, time
            tmp = Path(tempfile.gettempdir()) / f"decoded_{int(time.time())}.parquet"
            try:
                df.to_parquet(tmp, index=False, engine='pyarrow')
            except Exception:
                # fallback to fastparquet if available
                df.to_parquet(tmp, index=False)
            ui.download(tmp)
            self.show_success(f'Exported Parquet: {tmp.name}')
        except Exception as ex:
            self.show_error(f'Parquet export failed: {str(ex)}')


def create_ui():
    analyzer = CANLogAnalyzerUI()

    ui.add_head_html('''
        <style>
            /* Theme Variables: light & dark */
            :root[data-theme="dark"] {
                --bg: #0d1117;
                --bg-subtle: #161b22;
                --border: #30363d;
                --text: #c9d1d9;
                --muted: #8b949e;
                --accent: #2f81f7;
                --success: #2ea043;
                --danger: #f85149;
                --warn: #d29922;
                --mark: #39d353;
            }
            :root[data-theme="light"] {
                --bg: #ffffff;
                --bg-subtle: #f6f8fa;
                --border: #d0d7de;
                --text: #24292f;
                --muted: #57606a;
                --accent: #0969da;
                --success: #1a7f37;
                --danger: #cf222e;
                --warn: #9a6700;
                --mark: #0969da;
            }
            * { box-sizing: border-box; }
            body {
                background: var(--bg);
                color: var(--text);
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
                font-size: 14px; /* increased for readability */
            }
            .arcade-header {
                background: linear-gradient(90deg, color-mix(in oklab, var(--accent) 15%, transparent) 0%, color-mix(in oklab, var(--mark) 15%, transparent) 100%);
                border-bottom: 1px solid var(--border);
                box-shadow: 0 1px 0 rgba(240, 246, 252, 0.05);
                padding: 6px !important;
                min-height: auto !important;
            }
            .arcade-card {
                background: var(--bg-subtle) !important;
                border: 1px solid var(--border) !important;
                border-radius: 6px !important;
                box-shadow: 0 0 0 1px rgba(240,246,252,0.02), 0 8px 24px rgba(1,4,9,0.4);
                padding: 6px !important;
            }
            .arcade-title { color: var(--text); font-size: 0.9rem; font-weight: 700; letter-spacing: .02em; }
            .arcade-label { color: var(--muted); font-size: 0.8rem; margin-bottom: 2px; }
            .arcade-status {
                color: var(--mark);
                font-size: 0.85rem;
                padding: 6px;
                border: 1px solid var(--border);
                border-left: 3px solid var(--mark);
                border-radius: 6px;
                background: color-mix(in oklab, var(--mark) 8%, transparent);
            }
            .arcade-button {
                background: linear-gradient(180deg, color-mix(in oklab, var(--accent) 15%, transparent) 0%, color-mix(in oklab, var(--accent) 5%, transparent) 100%) !important;
                border: 1px solid var(--border) !important;
                color: var(--text) !important;
                font-size: 0.85rem !important;
                padding: 8px 12px !important;
                min-height: auto !important;
            }
            .arcade-button:hover { border-color: var(--accent) !important; box-shadow: 0 0 0 2px color-mix(in oklab, var(--accent) 25%, transparent); }
            .q-field__control { background: var(--bg) !important; border: 1px solid var(--border) !important; border-radius: 6px !important; min-height: 32px !important; }
            .q-field__label { color: var(--muted) !important; font-size: 0.8rem !important; }
            .q-field__native { font-size: 0.9rem !important; padding: 4px 8px !important; color: var(--text) !important; }
            .q-select__dropdown-icon { color: var(--muted) !important; }
            .q-menu, .q-list, .q-item { background: var(--bg-subtle) !important; color: var(--text) !important; }
            .q-item--active { background: color-mix(in oklab, var(--accent) 15%, transparent) !important; }
            .q-uploader { min-height: auto !important; background: var(--bg) !important; border: 1px dashed var(--border) !important; }
            .q-uploader__header { min-height: 30px !important; padding: 4px 8px !important; background: var(--bg-subtle) !important; border-bottom: 1px solid var(--border) !important; }
            .q-uploader__header * { font-size: 0.85rem !important; color: var(--text) !important; }
            .q-uploader__list { padding: 2px 6px !important; }
            .q-uploader, .q-uploader__list, .q-uploader__header .q-btn { font-size: 0.85rem !important; }
        </style>
        <script>
            // Set default theme on load
            document.documentElement.setAttribute('data-theme','dark');
        </script>
    ''')

    with ui.header().classes('arcade-header'):
        with ui.row().classes('items-center justify-between w-full'):
            ui.label('🎮 CAN LOG ANALYZER 🎮').classes('text-base font-bold')
            analyzer.theme_toggle = ui.toggle({'light': '☀️ Light', 'dark': '🌑 Dark'}, value='dark', on_change=analyzer.on_theme_toggle).props('dense')

    with ui.column().classes('w-full p-1 gap-1'):
        analyzer.status_label = ui.label('⚡ READY TO LOAD FILES ⚡').classes('arcade-status w-full text-center')

        # Row 1: Single card with LOAD FILES (one row) and SELECT DATA (below)
        with ui.card().classes('w-full arcade-card'):
            with ui.column().classes('w-full gap-1'):
                # LOAD FILES
                ui.label('LOAD FILES').classes('arcade-title mb-2')
                with ui.row().classes('w-full gap-2'):
                    with ui.column().classes('flex-1 gap-1'):
                        ui.label('DATABASE FILE (DBC/ARXML):').classes('arcade-label')
                        ui.upload(label='Upload Database', on_upload=analyzer.handle_database_upload, auto_upload=True).classes('w-full q-pa-xs q-ma-none text-xs').props('accept=.dbc,.arxml color=purple')
                    with ui.column().classes('flex-1 gap-1'):
                        ui.label('LOG FILE (BLF/ASC):').classes('arcade-label')
                        ui.upload(label='Upload Log File', on_upload=analyzer.handle_log_upload, auto_upload=True).classes('w-full q-pa-xs q-ma-none text-xs').props('accept=.blf,.asc color=pink')

                # SELECT DATA below
                ui.label('SELECT DATA').classes('arcade-title mt-2')
                with ui.column().classes('gap-2 w-full'):
                    ui.label('CAN CHANNEL:').classes('arcade-label')
                    analyzer.channel_select = ui.select(options=[], label='Select Channel', on_change=analyzer.on_channel_selected).classes('w-full').props('dense options-dense')
                    analyzer.channel_select.set_enabled(False)

                    ui.label('MESSAGES:').classes('arcade-label')
                    analyzer.message_select = ui.select(options={}, label='Select Messages', multiple=True, on_change=analyzer.on_messages_selected).classes('w-full').props('dense options-dense')
                    analyzer.message_select.set_enabled(False)

                    ui.label('SIGNALS:').classes('arcade-label')
                    analyzer.signal_select = ui.select(options={}, label='Select Signals', multiple=True, on_change=analyzer.on_signals_selected).classes('w-full').props('dense options-dense')
                    analyzer.signal_select.set_enabled(False)
                    with ui.row().classes('w-full gap-2'):
                        ui.button('🧹 Clear Selections', on_click=analyzer.clear_selections).classes('w-full arcade-button').props('dense')

        # Row 2: Plot Config (full width)
        with ui.card().classes('w-full arcade-card'):
            ui.label('PLOT CONFIG').classes('arcade-title mb-2')
            # single-row config: mode + range + max points + actions
            with ui.row().classes('w-full gap-1 items-end flex-nowrap'):
                analyzer.plot_mode_select = ui.select(
                    options={'separate': '🎯 SEPARATE', 'combined': '🌟 COMBINED'},
                    value='separate',
                    label='Mode'
                ).props('dense options-dense')
                analyzer.time_start_input = ui.number(label='Start', value=None).props('dense')
                analyzer.time_end_input = ui.number(label='End', value=None).props('dense')
                analyzer.max_points_input = ui.number(label='Max points', value=5000, min=100, step=100).props('dense')
                ui.button('🚀 Generate', on_click=analyzer.plot_signals).classes('arcade-button').props('dense')
                ui.button('⬇️ CSV', on_click=analyzer.export_csv).classes('arcade-button').props('dense')
                ui.button('⬇️ Parquet', on_click=analyzer.export_parquet).classes('arcade-button').props('dense')

        # Row 3: Signal Plots (full width)
        with ui.card().classes('w-full arcade-card'):
            ui.label('SIGNAL PLOTS 📊').classes('arcade-title mb-2')
            analyzer.plot_container = ui.column().classes('w-full gap-2')
