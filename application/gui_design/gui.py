import math
import threading
import os
import random
import dearpygui.dearpygui as dpg
import time
import serial.tools.list_ports

"""Desktop GUI for CSAimBot control, telemetry, and settings."""

# IMPORTANT:
# X is the end stop near the motor.
# Y is the carriage axis with the gripper.
from utils.json_utils import StatsManager


class GUI:
    """Main Dear PyGui application wrapper."""

    def __init__(self, vision_pipe, comms_pipe, sim_pipe, mouse_blocker_pipe=None):
        """
        Initialize the GUI and wire up IPC channels.

        Args:
            vision_pipe: Pipe used to communicate with the vision worker.
            comms_pipe: Pipe used to communicate with the serial worker.
            sim_pipe: Pipe used to communicate with the simulation worker.
            mouse_blocker_pipe: Pipe used to start/stop the mouse blocker worker.
        """
        self.pipe = vision_pipe
        self.comms_pipe = comms_pipe
        self.sim_pipe = sim_pipe
        self.mouse_blocker_pipe = mouse_blocker_pipe
        self.simulation_state = "stopped"
        self.running = True
        self.sidebar_expanded = False
        self.stats_manager = StatsManager()
        self._last_stats_refresh = 0

        self.is_connected = False
        self.connection_msg = (
            "Connected to ESP32" if self.is_connected else "No connection to ESP32"
        )
        self.connection_state = "disconnected"

        # Manual/display coordinates used by the GUI controls only.
        self.pos_x = 0
        self.pos_y = 0
        self.pos_z = 0

        # Vision target offsets from aimbot.py.
        # These must NOT be mixed with manual jog coordinates.
        self.target_offset_x = 0
        self.target_offset_y = 0
        self.manual_keys = ""
        self.current_speed = 75
        # PID Controller variables for visual servoing
        self.kp = 0.4  # Proportional gain (depends on current error)
        self.ki = 0.0  # Integral gain (depends on sum of past errors)
        self.kd = 0.1  # Derivative gain (depends on rate of error change)
        self.pid_integral = 0.0
        self.pid_prev_error = 0.0
        self.pid_last_time = time.time()
        self.current_scale = 1.0

        # Dictionary for smart management of forced dimension responsiveness
        self.layout_elements = {}

        self.active_page_tag = "page_home"
        self.nav_config = {
            "page_home": {
                "label": "Home Page",
                "active_tex": "tex_home",
                "inactive_tex": "tex_home_inactive",
            },
            "page_control": {
                "label": "Control Panel",
                "active_tex": "tex_control",
                "inactive_tex": "tex_control_inactive",
            },
            "page_simulation": {
                "label": "Simulation",
                "active_tex": "tex_control",
                "inactive_tex": "tex_control_inactive",
            },
            "page_stat": {
                "label": "Statistics",
                "active_tex": "tex_stat",
                "inactive_tex": "tex_stat_inactive",
            },
            "page_settings": {
                "label": "Settings",
                "active_tex": "tex_settings",
                "inactive_tex": "tex_settings_inactive",
            },
        }
        self.nav_elements = {}
        self.current_lang = "English"
        self.lang_dict = {
            "English": {
                "nav_home": "Home Page",
                "nav_control": "Control Panel",
                "nav_simulation": "Simulation",
                "nav_stat": "Statistics",
                "nav_settings": "Settings",
                "start": "START",
                "cal": "CALIBRATE",
                "stop": "FORCE STOP",
                "lang": "Language",
                "res": "Resolution",
                "port": "COM Port",
                "status_ok": "Status: OK",
                "status_err": "Error: ",
                "target": "Target Prioritization:",
                "logs": "System Logs:",
                "opencv": "Show OpenCV window",
                "lmb": "Press LMB",
                "rmb": "Press RMB",
                "gripper": "Gripper Test",
                "set0": "Set 0",
                "homing": "Homing",
                "centering": "Centering",
                "plot_data": "Data",
                "plot_vision": "Vision Data",
                "speed": "Speed",
                "stat_lmb_title": "LMB Clicked",
                "stat_lmb_desc": "How many times has the bot clicked left mouse button",
                "stat_rmb_title": "RMB Clicked",
                "stat_rmb_desc": "How many times has the bot clicked right mouse button",
                "stat_time_title": "Time ON",
                "stat_time_desc": "Amount time while the bot has been connected and turned on",
                "stat_mouse_title": "Mouses calibrated",
                "stat_mouse_desc": "Amount of mouses calibrated by the bot",
                "stat_dist_title": "Distance Traveled",
                "stat_dist_desc": "Total distance traveled by a mouse",
                "stat_energy_title": "Energy wasted",
                "stat_energy_desc": "Aproximated amount of energy used by the bot",
                "stat_unknown_title": "???",
                "stat_unknown_desc": "???",
                "stat_keys_title": "Keys pressed",
                "stat_keys_desc": "Amount of key presses by a user",
                "refresh": "Refresh",
            },
            "Polski": {
                "nav_home": "Strona Główna",
                "nav_control": "Panel Sterowania",
                "nav_simulation": "Symulacja",
                "nav_stat": "Statystyki",
                "nav_settings": "Ustawienia",
                "start": "START",
                "cal": "KALIBRUJ",
                "stop": "WYMUŚ STOP",
                "lang": "Język",
                "res": "Rozdzielczość",
                "port": "Port COM",
                "status_ok": "Status: OK",
                "status_err": "Błąd: ",
                "target": "Priorytet Celu:",
                "logs": "Logi Systemowe:",
                "opencv": "Pokaż okno OpenCV",
                "lmb": "Wciśnij LPM",
                "rmb": "Wciśnij PPM",
                "gripper": "Test Chwytaka",
                "set0": "Ustaw 0",
                "homing": "Homing",
                "centering": "Centrowanie",
                "plot_data": "Dane",
                "plot_vision": "Dane Wizyjne",
                "speed": "Prędkość",
                "stat_lmb_title": "Kliknięcia LPM",
                "stat_lmb_desc": "Ile razy bot kliknął lewy przycisk myszy",
                "stat_rmb_title": "Kliknięcia PPM",
                "stat_rmb_desc": "Ile razy bot kliknął prawy przycisk myszy",
                "stat_time_title": "Czas działania",
                "stat_time_desc": "Czas, przez który bot był połączony i włączony",
                "stat_mouse_title": "Skalibrowane myszy",
                "stat_mouse_desc": "Ilość myszy skalibrowanych przez bota",
                "stat_dist_title": "Przebyty dystans",
                "stat_dist_desc": "Całkowity dystans przebyty przez mysz",
                "stat_energy_title": "Zużyta energia",
                "stat_energy_desc": "Przybliżona ilość energii zużytej przez bota",
                "stat_unknown_title": "???",
                "stat_unknown_desc": "???",
                "stat_keys_title": "Wciśnięte klawisze",
                "stat_keys_desc": "Ilość klawiszy wciśniętych przez użytkownika",
                "refresh": "Odśwież",
            },
        }
        dpg.create_context()
        self.width = 1280
        self.height = 720

        # FIX: Locking min and max window sizes naturally disables the Windows maximize button
        dpg.create_viewport(
            title="CSAimBot Control Panel",
            width=self.width,
            height=self.height,
            resizable=False,
            min_width=self.width,
            max_width=self.width,
            min_height=self.height,
            max_height=self.height,
        )
        dpg.setup_dearpygui()

        self.setup_fonts()
        self.setup_themes()
        self.load_textures()
        self.build_ui()

        self.listener_thread = threading.Thread(target=self.poll_pipe, daemon=True)
        self.listener_thread.start()

        self.sim_pipe.send({"cmd": "STATUS"})
        self.on_language_change(None, "English")
        self.update_simulation_display()

        # Initialize and display available COM ports correctly
        self.refresh_ports()

    def rs(self, w=None, h=None, pos=None, wrap=None, tag=None):
        """Register base UI constraints for high-quality scaling logic."""
        if tag is None:
            tag = dpg.generate_uuid()
        self.layout_elements[tag] = {"w": w, "h": h, "pos": pos, "wrap": wrap}
        return tag

    def on_resolution_change(self, sender, app_data):
        """Smoothly switches resolution using dedicated fonts, preserving quality."""
        try:
            new_w, new_h = map(int, app_data.split("x"))
            self.current_scale = new_w / 1280.0
            self.width = new_w
            self.height = new_h

            # Configure viewport with hard bounds to keep maximize button disabled
            dpg.configure_viewport(
                0,
                width=self.width,
                height=self.height,
                min_width=self.width,
                max_width=self.width,
                min_height=self.height,
                max_height=self.height,
            )

            # Switch to the appropriate font, avoiding ugly blur
            if (
                hasattr(self, "font_720")
                and self.font_720
                and hasattr(self, "font_1080")
                and self.font_1080
            ):
                dpg.bind_font(
                    self.font_1080 if self.current_scale > 1.1 else self.font_720
                )

            # Update the base width of the sidebar before scaling, if expanded
            base_w = 235 if self.sidebar_expanded else 60
            if "window_sidebar" in self.layout_elements:
                self.layout_elements["window_sidebar"]["w"] = base_w
            if "sidebar_child" in self.layout_elements:
                self.layout_elements["sidebar_child"]["w"] = base_w

            # Apply native proportion changes to registered, fixed elements
            for tag, base in self.layout_elements.items():
                if dpg.does_item_exist(tag):
                    kwargs = {}
                    if base["w"] is not None:
                        kwargs["width"] = int(base["w"] * self.current_scale)
                    if base["h"] is not None:
                        kwargs["height"] = int(base["h"] * self.current_scale)
                    if base["pos"] is not None:
                        kwargs["pos"] = [
                            int(base["pos"][0] * self.current_scale),
                            int(base["pos"][1] * self.current_scale),
                        ]
                    if base["wrap"] is not None:
                        kwargs["wrap"] = int(base["wrap"] * self.current_scale)

                    if kwargs:
                        dpg.configure_item(tag, **kwargs)

        except Exception as e:
            print(f"Error during resolution change: {e}")

    def switch_page(self, sender, app_data, user_data):
        """Switch the visible page in the main window.

        Args:
            user_data: Tag of the page that should be shown.
        """
        pages = [
            "page_home",
            "page_control",
            "page_simulation",
            "page_stat",
            "page_settings",
        ]
        for page in pages:
            if dpg.does_item_exist(page):
                dpg.configure_item(page, show=(page == user_data))

        self.active_page_tag = user_data

        if self.sidebar_expanded:
            self.toggle_sidebar(None, None)

    def setup_fonts(self):
        """Loads two font sizes for perfect responsiveness and text quality."""
        import sys

        if getattr(sys, "frozen", False):
            current_dir = os.path.join(getattr(sys, "_MEIPASS"), "application", "gui_design")
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(current_dir, "fonts", "Roboto.ttf")

        self.font_720 = None
        self.font_1080 = None

        with dpg.font_registry():
            if os.path.exists(font_path):
                # Standard font for 720p
                with dpg.font(font_path, 17) as f720:
                    dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                    dpg.add_font_range(0x0100, 0x017F)
                    self.font_720 = f720

                # Large native font for 1080p, guaranteeing readability
                with dpg.font(font_path, 26) as f1080:
                    dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                    dpg.add_font_range(0x0100, 0x017F)
                    self.font_1080 = f1080

                dpg.bind_font(self.font_720)

    def create_rbtn_theme(self, bg_color, hover_color, dot_color, text_color):
        """Create a radio button theme.

        Args:
            bg_color: Normal frame background color.
            hover_color: Hover state background color.
            dot_color: Check mark color.
            text_color: Label text color.

        Returns:
            Dear PyGui theme identifier.
        """
        with dpg.theme() as theme_id:
            with dpg.theme_component(dpg.mvRadioButton):
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, bg_color)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, hover_color)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, bg_color)
                dpg.add_theme_color(dpg.mvThemeCol_CheckMark, dot_color)
                dpg.add_theme_color(dpg.mvThemeCol_Text, text_color)
        return theme_id

    def setup_themes(self):
        """Create the shared themes used across the interface."""
        with dpg.theme() as self.global_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, [54, 57, 63, 255])
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, [16, 16, 17, 255])
                dpg.add_theme_color(dpg.mvThemeCol_Text, [255, 215, 0, 255])
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 10, 10)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)

            with dpg.theme_component(dpg.mvPlot):
                dpg.add_theme_color(dpg.mvPlotCol_PlotBg, [25, 25, 30, 255])
                dpg.add_theme_color(dpg.mvPlotCol_PlotBorder, [31, 35, 42, 255])

        self.gray_btn_theme = self.create_btn_theme(
            [54, 60, 70], [70, 70, 70], [30, 30, 30]
        )
        self.green_btn_theme = self.create_btn_theme(
            [50, 200, 50], [70, 255, 70], [30, 150, 30]
        )
        self.red_btn_theme = self.create_btn_theme(
            [200, 0, 0], [220, 0, 0], [180, 0, 0]
        )
        self.gold_btn_theme = self.create_btn_theme(
            [255, 190, 25], [255, 200, 0], [255, 160, 0], [40, 40, 60]
        )
        self.transparent_btn_theme = self.create_btn_theme(
            [0, 0, 0, 0], [255, 255, 255, 20], [255, 255, 255, 40]
        )

        self.yellow_rbtn_theme = self.create_rbtn_theme(
            [50, 50, 0], [70, 70, 0], [255, 255, 0], [255, 255, 255]
        )
        self.blue_rbtn_theme = self.create_rbtn_theme(
            [0, 0, 50], [0, 0, 70], [0, 255, 255], [255, 255, 255]
        )
        self.violet_rbtn_theme = self.create_rbtn_theme(
            [50, 0, 50], [70, 0, 70], [255, 0, 255], [255, 255, 255]
        )

        with dpg.theme() as self.white_text_theme:
            with dpg.theme_component(dpg.mvText):
                dpg.add_theme_color(dpg.mvThemeCol_Text, [255, 255, 255, 255])

        with dpg.theme() as self.gray_text_theme:
            with dpg.theme_component(dpg.mvText):
                dpg.add_theme_color(dpg.mvThemeCol_Text, [50, 50, 80, 255])

        with dpg.theme() as self.gold_text_theme:
            with dpg.theme_component(dpg.mvText):
                dpg.add_theme_color(dpg.mvThemeCol_Text, [255, 190, 25, 255])

        with dpg.theme() as self.dim_theme:
            with dpg.theme_component(dpg.mvWindowAppItem):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, [0, 0, 0, 180])
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)

        with dpg.theme() as self.slider_theme:
            with dpg.theme_component(dpg.mvSliderInt):
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, [54, 60, 70, 255])
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, [255, 183, 0, 255])
                dpg.add_theme_style(dpg.mvStyleVar_GrabRounding, 12)

        with dpg.theme() as self.root_theme:
            with dpg.theme_component(dpg.mvWindowAppItem):
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, [27, 26, 33, 255])

        with dpg.theme() as self.sidebar_theme:
            with dpg.theme_component(dpg.mvWindowAppItem):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, [27, 26, 33, 255])
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)

        with dpg.theme() as self.settings_row_theme:
            with dpg.theme_component(dpg.mvChildWindow):
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, [30, 32, 38, 255])
                dpg.add_theme_color(dpg.mvThemeCol_Border, [0, 0, 0, 0])
                dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 8)
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 13)

        with dpg.theme() as self.gold_combo_theme:
            with dpg.theme_component(dpg.mvCombo):
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, [255, 190, 25, 255])
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, [255, 200, 0, 255])
                dpg.add_theme_color(dpg.mvThemeCol_Text, [0, 0, 0, 255])
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)

        with dpg.theme() as self.stat_card_theme:
            with dpg.theme_component(dpg.mvChildWindow):
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, [28, 30, 36, 255])
                dpg.add_theme_color(dpg.mvThemeCol_Border, [0, 0, 0, 0])
                dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 8)
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 15, 15)

        with dpg.theme() as self.stat_value_theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, [54, 60, 70, 255])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, [54, 60, 70, 255])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, [54, 60, 70, 255])
                dpg.add_theme_color(dpg.mvThemeCol_Text, [255, 255, 255, 255])
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)
                dpg.add_theme_style(dpg.mvStyleVar_ButtonTextAlign, 0.5, 0.5)

        self.invisible_btn_theme = self.create_btn_theme(
            [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]
        )

    def create_btn_theme(
        self, color, hover_color, active_color, text_color=[255, 255, 255]
    ):
        """Create a button theme.

        Args:
            color: Default button color.
            hover_color: Hover state color.
            active_color: Pressed state color.
            text_color: Button text color.

        Returns:
            Dear PyGui theme identifier.
        """
        with dpg.theme() as theme_id:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, color)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, hover_color)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, active_color)
                dpg.add_theme_color(dpg.mvThemeCol_Text, text_color)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)
            with dpg.theme_component(dpg.mvImageButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, color)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, hover_color)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, active_color)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)
        return theme_id

    def load_textures(self):
        """Load image assets into Dear PyGui textures."""
        import sys

        if getattr(sys, "frozen", False):
            current_dir = os.path.join(getattr(sys, "_MEIPASS"), "application", "gui_design")
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))

        with dpg.texture_registry(show=False):

            def load_and_add(rel_path, tag):
                path_parts = rel_path.split("/")
                full_path = os.path.join(current_dir, *path_parts)
                try:
                    img = dpg.load_image(full_path)
                    if img:
                        dpg.add_static_texture(
                            width=img[0], height=img[1], default_value=img[3], tag=tag
                        )
                    else:
                        dpg.add_static_texture(
                            width=1,
                            height=1,
                            default_value=[0.0, 0.0, 0.0, 0.0],
                            tag=tag,
                        )
                except Exception:
                    dpg.add_static_texture(
                        width=1, height=1, default_value=[0.0, 0.0, 0.0, 0.0], tag=tag
                    )

            load_and_add("icons/ikona_hamburger.png", "tex_menu")
            load_and_add("icons/ikona_X.png", "tex_x")
            load_and_add("icons/connect/ikona_connect_red.png", "tex_connect_red")
            load_and_add("icons/ikona_connect_yellow.png", "tex_connect_yellow")
            load_and_add("icons/ikona_connect_green.png", "tex_connect_green")
            load_and_add("icons/ikona_home.png", "tex_home")
            load_and_add("icons/ikona_control.png", "tex_control")
            load_and_add("icons/ikona_stat.png", "tex_stat")
            load_and_add("icons/ikona_settings.png", "tex_settings")
            load_and_add("icons/ikona_home_inactive.png", "tex_home_inactive")
            load_and_add("icons/ikona_control_inactive.png", "tex_control_inactive")
            load_and_add("icons/ikona_stat_inactive.png", "tex_stat_inactive")
            load_and_add("icons/ikona_settings_inactive.png", "tex_settings_inactive")
            load_and_add("icons/connect/ikona_connect_red.png", "tex_conn_red")
            load_and_add(
                "icons/connect/ikona_connect_red_full.png", "tex_conn_red_full"
            )
            load_and_add("icons/connect/ikona_connect_green.png", "tex_conn_green")
            load_and_add(
                "icons/connect/ikona_connect_green_full.png", "tex_conn_green_full"
            )
            load_and_add("icons/connect/ikona_connect_yellow.png", "tex_conn_yellow")
            load_and_add(
                "icons/connect/ikona_connect_yellow_full1.png", "tex_conn_yellow_full1"
            )
            load_and_add(
                "icons/connect/ikona_connect_yellow_full2.png", "tex_conn_yellow_full2"
            )
            load_and_add("icons/stats/ikona_lmb.png", "tex_stat_lmb")
            load_and_add("icons/stats/ikona_rmb.png", "tex_stat_rmb")
            load_and_add("icons/stats/ikona_time.png", "tex_stat_time")
            load_and_add("icons/stats/ikona_mouse.png", "tex_stat_mouse")
            load_and_add("icons/stats/ikona_dist.png", "tex_stat_dist")
            load_and_add("icons/stats/ikona_energy.png", "tex_stat_energy")
            load_and_add("icons/stats/ikona_keys.png", "tex_stat_keys")

    def toggle_sidebar(self, sender, app_data):
        """Expand or collapse the navigation sidebar."""
        self.sidebar_expanded = not self.sidebar_expanded
        base_w = 235 if self.sidebar_expanded else 60

        # Base updated within the responsive registry
        if "window_sidebar" in self.layout_elements:
            self.layout_elements["window_sidebar"]["w"] = base_w
        if "sidebar_child" in self.layout_elements:
            self.layout_elements["sidebar_child"]["w"] = base_w

        new_width = int(base_w * getattr(self, "current_scale", 1.0))
        dpg.configure_item("window_sidebar", width=new_width)
        dpg.configure_item("sidebar_child", width=new_width)
        dpg.configure_item("window_dim", show=self.sidebar_expanded)

        if self.sidebar_expanded:
            dpg.focus_item("window_sidebar")

        if dpg.does_alias_exist("tex_menu") and dpg.does_alias_exist("tex_x"):
            dpg.configure_item(
                self.btn_toggle,
                texture_tag="tex_x" if self.sidebar_expanded else "tex_menu",
            )

        dpg.configure_item(self.title_text, show=self.sidebar_expanded)
        for txt in self.nav_texts:
            dpg.configure_item(txt, show=self.sidebar_expanded)

        if dpg.does_alias_exist("group_conn_icon") and dpg.does_alias_exist(
            "group_conn_full"
        ):
            dpg.configure_item("group_conn_icon", show=not self.sidebar_expanded)
            dpg.configure_item("group_conn_full", show=self.sidebar_expanded)
            dpg.configure_item("group_conn_text", show=self.sidebar_expanded)
            dpg.configure_item(
                "group_conn_text_placeholder", show=not self.sidebar_expanded
            )

    def add_nav_item(self, icon_or_texture_tag, text_label, page_tag):
        """Add a navigation button and label pair.

        Args:
            icon_or_texture_tag: Texture tag or fallback label for the button.
            text_label: Visible text shown in the expanded sidebar.
            page_tag: Tag of the page to show when selected.
        """
        with dpg.group(horizontal=True):
            if dpg.does_alias_exist(icon_or_texture_tag):
                btn = dpg.add_image_button(
                    texture_tag=icon_or_texture_tag,
                    width=50,
                    height=50,
                    callback=self.switch_page,
                    user_data=page_tag,
                    tag=self.rs(w=50, h=50),
                )
            else:
                btn = dpg.add_button(
                    label=icon_or_texture_tag,
                    width=50,
                    height=50,
                    callback=self.switch_page,
                    user_data=page_tag,
                    tag=self.rs(w=50, h=50),
                )

            dpg.bind_item_theme(btn, self.transparent_btn_theme)
            with dpg.group():
                dpg.add_spacer(height=15, tag=self.rs(h=15))
                txt = dpg.add_text(text_label, show=False)
                dpg.bind_item_theme(txt, self.gold_text_theme)
            self.nav_texts.append(txt)
        dpg.add_spacer(height=5, tag=self.rs(h=5))

    def on_language_change(self, sender, app_data):
        """Apply the selected language to the visible labels.

        Args:
            app_data: Selected language key.
        """
        self.current_lang = app_data
        t = self.lang_dict[self.current_lang]

        nav_mapping = {
            "page_home": "nav_home",
            "page_control": "nav_control",
            "page_stat": "nav_stat",
            "page_settings": "nav_settings",
        }
        for page_tag, dict_key in nav_mapping.items():
            tag = f"nav_text_{page_tag}"
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, t[dict_key])

        stat_ids = ["lmb", "rmb", "time", "mouse", "dist", "energy", "unknown", "keys"]
        for s_id in stat_ids:
            title_tag = f"stat_title_{s_id}"
            desc_tag = f"stat_desc_{s_id}"
            if dpg.does_item_exist(title_tag):
                dpg.set_value(title_tag, t[f"stat_{s_id}_title"])
            if dpg.does_item_exist(desc_tag):
                dpg.set_value(desc_tag, t[f"stat_{s_id}_desc"])

        button_tags = [
            ("btn_start_home", "start"),
            ("btn_start_control", "start"),
            ("btn_cal_home", "cal"),
            ("btn_cal_control", "cal"),
            ("btn_stop_home", "stop"),
            ("btn_stop_control", "stop"),
            ("btn_lmb_control", "lmb"),
            ("btn_rmb_control", "rmb"),
            ("btn_gripper_control", "gripper"),
            ("btn_homing_control", "homing"),
            ("btn_centering_control", "centering"),
            ("btn_set0_lmb", "set0"),
            ("btn_set0_rmb", "set0"),
            ("btn_set0_gripper", "set0"),
        ]
        for tag, dict_key in button_tags:
            if dpg.does_item_exist(tag):
                dpg.configure_item(tag, label=t[dict_key])

        text_tags = [
            ("txt_lang", "lang"),
            ("txt_res", "res"),
            ("txt_port", "port"),
            ("txt_target_home", "target"),
            ("txt_target_control", "target"),
            ("txt_logs_home", "logs"),
            ("txt_logs_control", "logs"),
        ]
        for tag, dict_key in text_tags:
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, t[dict_key])

        if dpg.does_item_exist("chk_debug_home"):
            dpg.configure_item("chk_debug_home", label=t["opencv"])
        if dpg.does_item_exist("chk_debug_control"):
            dpg.configure_item("chk_debug_control", label=t["opencv"])

        text_val = (
            t["status_ok"]
            if self.is_connected
            else f"{t['status_err']}{self.connection_msg}"
        )
        if hasattr(self, "conn_text") and dpg.does_item_exist(self.conn_text):
            dpg.set_value(self.conn_text, text_val)

        if dpg.does_item_exist("plot_home_1"):
            dpg.configure_item("plot_home_1", label=t["plot_data"])
        if dpg.does_item_exist("plot_home_2"):
            dpg.configure_item("plot_home_2", label=t["plot_data"])
        if dpg.does_item_exist("plot_control"):
            dpg.configure_item("plot_control", label=t["plot_vision"])

        if dpg.does_item_exist("speed_text_label_control") and dpg.does_item_exist(
            "slider_speed_control"
        ):
            curr_speed = dpg.get_value("slider_speed_control")
            dpg.set_value("speed_text_label_control", f"{t['speed']}: {curr_speed}%")

    def update_connection_display(self):
        """Refresh the connection icon and status text."""
        t = self.lang_dict[self.current_lang]
        icon_texture = "tex_conn_red"
        full_texture = "tex_conn_red_full"
        text_color = [255, 80, 80]
        display_text = f"{t['status_err']}{self.connection_msg}"

        if self.connection_state == "connected":
            icon_texture = "tex_conn_green"
            full_texture = "tex_conn_green_full"
            text_color = [80, 255, 80]
            display_text = t["status_ok"]
        elif self.connection_state == "connecting":
            icon_texture = "tex_conn_yellow"
            full_texture = "tex_conn_yellow_full1"
            text_color = [255, 255, 80]
            display_text = "Connecting..."
        elif self.connection_state == "disconnecting":
            icon_texture = "tex_conn_yellow"
            full_texture = "tex_conn_yellow_full2"
            text_color = [255, 255, 80]
            display_text = "Disconnecting..."

        if hasattr(self, "btn_connect_icon") and dpg.does_item_exist(
            self.btn_connect_icon
        ):
            dpg.configure_item(self.btn_connect_icon, texture_tag=icon_texture)
        if hasattr(self, "btn_connect_full") and dpg.does_item_exist(
            self.btn_connect_full
        ):
            dpg.configure_item(self.btn_connect_full, texture_tag=full_texture)
        if hasattr(self, "conn_text") and dpg.does_item_exist(self.conn_text):
            dpg.configure_item(self.conn_text, color=text_color)
            dpg.set_value(self.conn_text, display_text)

    def add_sim_controls(self, suffix):
        """Add simulation start and stop buttons for a page.

        Args:
            suffix: Page suffix used to build unique widget tags.
        """
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=14, tag=self.rs(w=14))
            btn_start_sim = dpg.add_button(
                label="START SIM",
                width=105,
                height=35,
                tag=self.rs(105, 35, tag=f"btn_start_sim_{suffix}"),
                callback=self.on_start_sim,
            )
            dpg.add_spacer(width=10, tag=self.rs(w=10))
            btn_stop_sim = dpg.add_button(
                label="STOP SIM",
                width=105,
                height=35,
                tag=self.rs(105, 35, tag=f"btn_stop_sim_{suffix}"),
                callback=self.on_stop_sim,
            )

        dpg.bind_item_theme(btn_start_sim, self.green_btn_theme)
        dpg.bind_item_theme(btn_stop_sim, self.red_btn_theme)

    def refresh_ports(self, sender=None, app_data=None):
        """Refresh the list of available COM ports and explicitly update the combo box value."""
        available_ports = [port.device for port in serial.tools.list_ports.comports()]
        if not available_ports:
            available_ports = ["COM3"]

        if dpg.does_item_exist("combo_port"):
            dpg.configure_item("combo_port", items=available_ports)
            # Explicitly setting value prevents Dear PyGui from displaying an empty box dynamically
            dpg.set_value("combo_port", available_ports[0])
            self.comms_pipe.send({"cmd": "CHANGE_PORT", "value": available_ports[0]})

    def on_sim_move(self, sender, app_data, user_data):
        """Handle directional movement in the simulation."""
        dx, dy = user_data
        step_size = 0.01
        self.sim_pipe.send(
            {"cmd": "SIM_MOVE", "dx": dx * step_size, "dy": dy * step_size}
        )

    def on_sim_center(self, sender, app_data):
        """Center the platform in the simulation."""
        self.sim_pipe.send({"cmd": "SIM_CENTER"})

    def on_sim_z_axis(self, sender, app_data, user_data):
        """Move the Z axis up or down in the simulation."""
        self.sim_pipe.send({"cmd": "SIM_Z_AXIS", "is_up": user_data})

    def on_sim_gripper(self, sender, app_data, user_data):
        """Open or close the gripper in the simulation."""
        self.sim_pipe.send({"cmd": "SIM_GRIPPER", "close": user_data})

    def on_sim_click(self, sender, app_data, user_data):
        """Simulate a mouse click."""
        if user_data == "left":
            self.sim_pipe.send({"cmd": "SIM_LEFT_CLICK"})
        else:
            self.sim_pipe.send({"cmd": "SIM_RIGHT_CLICK"})

    def on_sim_go(self, sender, app_data):
        """Move to a specific coordinate and shoot."""
        try:
            target_x = float(dpg.get_value(self.input_sim_x))
            target_y = float(dpg.get_value(self.input_sim_y))
            self.sim_pipe.send(
                {"cmd": "SIM_GO_AND_CLICK", "x": target_x, "y": target_y}
            )
        except ValueError:
            pass

    def build_ui(self):
        """Construct the full Dear PyGui interface."""
        dpg.bind_theme(self.global_theme)
        with dpg.window(
            tag=self.rs(self.width, self.height, tag="window_root"),
            width=self.width,
            height=self.height,
            no_title_bar=True,
            no_resize=True,
            no_move=True,
        ):
            dpg.bind_item_theme("window_root", self.root_theme)

            with dpg.group(tag="page_home", show=True):
                dpg.add_spacer(height=30, tag=self.rs(h=30))
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=100, tag=self.rs(w=100))
                    with dpg.group():
                        with dpg.group(horizontal=True):
                            with dpg.child_window(
                                width=520, height=300, tag=self.rs(520, 300)
                            ):
                                with dpg.plot(
                                    label="Dane", width=-1, height=-1, tag="plot_home_1"
                                ):
                                    dpg.add_plot_axis(dpg.mvXAxis, tag="home_plot1_x")
                                    dpg.add_plot_axis(dpg.mvYAxis, tag="home_plot1_y")

                                    x_data_1 = sorted(
                                        [random.uniform(50000, 60000) for _ in range(8)]
                                    )
                                    y_data_1 = [random.uniform(1, 7) for _ in range(8)]

                                    dpg.add_line_series(
                                        x_data_1, y_data_1, parent="home_plot1_y"
                                    )
                                    dpg.add_scatter_series(
                                        x_data_1, y_data_1, parent="home_plot1_y"
                                    )

                            dpg.add_spacer(width=20, tag=self.rs(w=20))

                            with dpg.child_window(
                                width=520, height=300, tag=self.rs(520, 300)
                            ):
                                with dpg.plot(
                                    label="Dane", width=-1, height=-1, tag="plot_home_2"
                                ):
                                    dpg.add_plot_axis(dpg.mvXAxis, tag="home_plot2_x")
                                    dpg.add_plot_axis(dpg.mvYAxis, tag="home_plot2_y")

                                    x_data_2 = sorted(
                                        [random.uniform(50000, 60000) for _ in range(8)]
                                    )
                                    y_data_2 = [random.uniform(1, 7) for _ in range(8)]

                                    dpg.add_line_series(
                                        x_data_2, y_data_2, parent="home_plot2_y"
                                    )
                                    dpg.add_scatter_series(
                                        x_data_2, y_data_2, parent="home_plot2_y"
                                    )

                        dpg.add_spacer(height=40, tag=self.rs(h=40))

                        with dpg.group(horizontal=True):
                            with dpg.group(width=200, tag=self.rs(w=200)):
                                btn_start_home = dpg.add_button(
                                    label="START",
                                    width=200,
                                    height=50,
                                    tag=self.rs(200, 50, tag="btn_start_home"),
                                    callback=self.on_start,
                                )
                                dpg.add_spacer(height=10, tag=self.rs(h=10))
                                btn_calibrate_home = dpg.add_button(
                                    label="CALIBRATE",
                                    width=200,
                                    height=50,
                                    tag=self.rs(200, 50, tag="btn_cal_home"),
                                    callback=self.on_calibrate,
                                )
                                dpg.add_spacer(height=10, tag=self.rs(h=10))
                                btn_stop_home = dpg.add_button(
                                    label="FORCE STOP",
                                    width=200,
                                    height=50,
                                    tag=self.rs(200, 50, tag="btn_stop_home"),
                                    callback=self.on_stop,
                                )

                                dpg.bind_item_theme(btn_start_home, self.gray_btn_theme)
                                dpg.bind_item_theme(
                                    btn_calibrate_home, self.gold_btn_theme
                                )
                                dpg.bind_item_theme(btn_stop_home, self.red_btn_theme)

                                dpg.add_spacer(height=5, tag=self.rs(h=5))

                                txt_target = dpg.add_text(
                                    "Target Prioritization:", tag="txt_target_home"
                                )
                                dpg.bind_item_theme(txt_target, self.gold_text_theme)

                                self.rbtn_target = dpg.add_radio_button(
                                    items=["ALL", "TT", "CT"],
                                    default_value="ALL",
                                    horizontal=True,
                                    tag="rbtn_target_home",
                                    callback=self.on_target_change,
                                )
                                dpg.bind_item_theme(
                                    self.rbtn_target, self.violet_rbtn_theme
                                )

                                dpg.add_spacer(height=5, tag=self.rs(h=5))
                                chk_debug = dpg.add_checkbox(
                                    label="Show OpenCV window",
                                    default_value=True,
                                    tag="chk_debug_home",
                                    callback=self.on_debug_toggle,
                                )

                            dpg.add_spacer(width=60, tag=self.rs(w=60))

                            with dpg.child_window(
                                width=470, height=220, tag=self.rs(470, 220)
                            ):
                                dpg.add_spacer(height=10, tag=self.rs(h=10))
                                with dpg.group(horizontal=True):
                                    dpg.add_spacer(width=10, tag=self.rs(w=10))
                                    with dpg.group():
                                        dpg.add_text(
                                            "System Logs:", color=[255, 183, 0]
                                        )
                                        with dpg.group(tag="logs_group_home"):
                                            dpg.add_text(
                                                "<System> Robot Control Active",
                                                color=[255, 255, 255],
                                            )
                                        dpg.bind_item_theme(
                                            "logs_group_home", self.white_text_theme
                                        )
                                        dpg.add_spacer(height=20, tag=self.rs(h=20))
                                        dpg.add_text(
                                            "Wciśnięte klawisze:", color=[255, 183, 0]
                                        )
                                        dpg.add_text(
                                            "[ BRAK ]",
                                            tag="current_keys_text",
                                            color=[50, 200, 50],
                                        )

                            dpg.add_spacer(width=33, tag=self.rs(w=33))

                            with dpg.group():
                                with dpg.child_window(
                                    width=280, height=165, tag=self.rs(280, 165)
                                ):
                                    dpg.add_spacer(height=16, tag=self.rs(h=16))
                                    axes = ["X", "Y", "Z"]
                                    for axis in axes:
                                        with dpg.group(horizontal=True):
                                            dpg.add_spacer(width=40, tag=self.rs(w=40))
                                            axis_label = dpg.add_text(f"{axis}: ")
                                            dpg.bind_item_theme(
                                                axis_label, self.white_text_theme
                                            )
                                            axis_value = dpg.add_text(
                                                "0.00", tag=f"coord_{axis.lower()}_home"
                                            )
                                            dpg.bind_item_theme(
                                                axis_value, self.white_text_theme
                                            )
                                        dpg.add_spacer(height=18, tag=self.rs(h=18))

            with dpg.group(tag="page_control", show=False):
                dpg.add_spacer(height=30, tag=self.rs(h=30))
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=100, tag=self.rs(w=100))
                    with dpg.group():
                        with dpg.group(horizontal=True):
                            with dpg.child_window(
                                width=560, height=300, tag=self.rs(560, 300)
                            ):
                                with dpg.plot(
                                    label="Dane Wizyjne",
                                    width=-1,
                                    height=-1,
                                    tag="plot_control",
                                ):
                                    dpg.add_plot_axis(dpg.mvXAxis, tag="control_plot_x")
                                    dpg.add_plot_axis(dpg.mvYAxis, tag="control_plot_y")
                                    dpg.add_line_series(
                                        list(range(100)),
                                        [math.cos(x / 10) for x in range(100)],
                                        parent="control_plot_y",
                                    )
                            dpg.add_spacer(width=20, tag=self.rs(w=20))
                            with dpg.child_window(
                                width=480, height=300, tag=self.rs(480, 300)
                            ):
                                dpg.add_spacer(height=10, tag=self.rs(h=10))
                                with dpg.group(horizontal=True):
                                    dpg.add_spacer(width=10, tag=self.rs(w=10))
                                    with dpg.group():
                                        dpg.add_text(
                                            "System Logs:", color=[255, 183, 0]
                                        )
                                        with dpg.group(tag="logs_group_control"):
                                            self.add_log(
                                                "<System> Robot Control Active",
                                                parent="logs_group_control",
                                            )
                                        dpg.bind_item_theme(
                                            "logs_group_control", self.white_text_theme
                                        )

                        dpg.add_spacer(height=40, tag=self.rs(h=40))

                        with dpg.group(horizontal=True):
                            with dpg.group():
                                btn_start = dpg.add_button(
                                    label="START",
                                    width=200,
                                    height=50,
                                    tag=self.rs(200, 50, tag="btn_start_control"),
                                    callback=self.on_start,
                                )
                                dpg.add_spacer(height=10, tag=self.rs(h=10))
                                btn_calibrate = dpg.add_button(
                                    label="CALIBRATE",
                                    width=200,
                                    height=50,
                                    tag=self.rs(200, 50, tag="btn_cal_control"),
                                    callback=self.on_calibrate,
                                )
                                dpg.add_spacer(height=10, tag=self.rs(h=10))
                                btn_stop = dpg.add_button(
                                    label="FORCE STOP",
                                    width=200,
                                    height=50,
                                    tag=self.rs(200, 50, tag="btn_stop_control"),
                                    callback=self.on_stop,
                                )

                                dpg.bind_item_theme(btn_start, self.gray_btn_theme)
                                dpg.bind_item_theme(btn_calibrate, self.gold_btn_theme)
                                dpg.bind_item_theme(btn_stop, self.red_btn_theme)

                                dpg.add_spacer(height=5, tag=self.rs(h=5))

                                txt_target = dpg.add_text("Target Prioritization:")
                                dpg.bind_item_theme(txt_target, self.gold_text_theme)

                                self.rbtn_target = dpg.add_radio_button(
                                    items=["ALL", "TT", "CT"],
                                    default_value="ALL",
                                    horizontal=True,
                                    # tag="rbtn_target_control", #o cos sie psuje gowno
                                    callback=self.on_target_change,
                                )
                                dpg.bind_item_theme(
                                    self.rbtn_target, self.violet_rbtn_theme
                                )

                                dpg.add_spacer(height=5, tag=self.rs(h=5))
                                self.chk_debug = dpg.add_checkbox(
                                    label="Show OpenCV window",
                                    default_value=True,
                                    callback=self.on_debug_toggle,
                                )

                            dpg.add_spacer(width=40, tag=self.rs(w=40))

                            with dpg.group():
                                # ROW 1: LMB (Half) + Homing (Half) + Jog + Set 0
                                with dpg.group(horizontal=True):
                                    btn_lmb = dpg.add_button(
                                        label="Press LMB",
                                        width=95,
                                        height=45,
                                        tag="btn_lpm_control",
                                    )
                                    dpg.add_spacer(width=10)
                                    btn_homing = dpg.add_button(
                                        label="Homing",
                                        width=95,
                                        height=45,
                                        tag="btn_homing_control",
                                    )
                                    dpg.bind_item_theme(btn_lmb, self.gold_btn_theme)
                                    dpg.bind_item_theme(btn_homing, self.gold_btn_theme)

                                    dpg.add_spacer(width=5)
                                    btn_left_lmb = dpg.add_button(
                                        label="<",
                                        width=70,
                                        height=45,
                                        callback=self.on_step_adjust,
                                        user_data=("lpm", -1),
                                        tag="btn_left_lpm",
                                    )
                                    dpg.bind_item_theme(
                                        btn_left_lmb, self.gold_btn_theme
                                    )

                                    dpg.add_spacer(width=5)
                                    btn_right_lmb = dpg.add_button(
                                        label=">",
                                        width=70,
                                        height=45,
                                        callback=self.on_step_adjust,
                                        user_data=("lpm", 1),
                                        tag="btn_right_lpm",
                                    )
                                    dpg.bind_item_theme(
                                        btn_right_lmb, self.gold_btn_theme
                                    )

                                    dpg.add_spacer(width=5)
                                    btn_set0_lmb = dpg.add_button(
                                        label="Set 0",
                                        width=80,
                                        height=45,
                                        tag="btn_set0_lpm",
                                        callback=self.on_set_zero,
                                        user_data="lpm",
                                    )
                                    dpg.bind_item_theme(
                                        btn_set0_lmb, self.gray_btn_theme
                                    )

                                dpg.add_spacer(height=10)

                                # ROW 2: RMB (Half) + Centering (Half) + Jog + Set 0
                                with dpg.group(horizontal=True):
                                    btn_rmb = dpg.add_button(
                                        label="Press RMB",
                                        width=95,
                                        height=45,
                                        tag="btn_ppm_control",
                                    )
                                    dpg.add_spacer(width=10)
                                    btn_centering = dpg.add_button(
                                        label="Centering",
                                        width=95,
                                        height=45,
                                        tag="btn_centering_control",
                                    )
                                    dpg.bind_item_theme(btn_rmb, self.gold_btn_theme)
                                    dpg.bind_item_theme(
                                        btn_centering, self.gold_btn_theme
                                    )

                                    dpg.add_spacer(width=5)
                                    btn_left_rmb = dpg.add_button(
                                        label="<",
                                        width=70,
                                        height=45,
                                        callback=self.on_step_adjust,
                                        user_data=("ppm", -1),
                                        tag="btn_left_ppm",
                                    )
                                    dpg.bind_item_theme(
                                        btn_left_rmb, self.gold_btn_theme
                                    )

                                    dpg.add_spacer(width=5)
                                    btn_right_rmb = dpg.add_button(
                                        label=">",
                                        width=70,
                                        height=45,
                                        callback=self.on_step_adjust,
                                        user_data=("ppm", 1),
                                        tag="btn_right_ppm",
                                    )
                                    dpg.bind_item_theme(
                                        btn_right_rmb, self.gold_btn_theme
                                    )

                                    dpg.add_spacer(width=5)
                                    btn_set0_rmb = dpg.add_button(
                                        label="Set 0",
                                        width=80,
                                        height=45,
                                        tag="btn_set0_ppm",
                                        callback=self.on_set_zero,
                                        user_data="ppm",
                                    )
                                    dpg.bind_item_theme(
                                        btn_set0_rmb, self.gray_btn_theme
                                    )

                                dpg.add_spacer(height=10)

                                # ROW 3: Gripper (Full width to match) + Jog + Set 0
                                with dpg.group(horizontal=True):
                                    btn_gripper = dpg.add_button(
                                        label="Gripper Test",
                                        width=215,
                                        height=45,
                                        tag="btn_test_control",
                                    )
                                    dpg.bind_item_theme(
                                        btn_gripper, self.gold_btn_theme
                                    )

                                    dpg.add_spacer(width=5)
                                    btn_left_gripper = dpg.add_button(
                                        label="<",
                                        width=70,
                                        height=45,
                                        callback=self.on_step_adjust,
                                        user_data=("test", -1),
                                        tag="btn_left_test",
                                    )
                                    dpg.bind_item_theme(
                                        btn_left_gripper, self.gold_btn_theme
                                    )

                                    dpg.add_spacer(width=5)
                                    btn_right_gripper = dpg.add_button(
                                        label=">",
                                        width=70,
                                        height=45,
                                        callback=self.on_step_adjust,
                                        user_data=("test", 1),
                                        tag="btn_right_test",
                                    )
                                    dpg.bind_item_theme(
                                        btn_right_gripper, self.gold_btn_theme
                                    )

                                    dpg.add_spacer(width=5)
                                    btn_set0_gripper = dpg.add_button(
                                        label="Set 0",
                                        width=80,
                                        height=45,
                                        tag="btn_set0_test",
                                        callback=self.on_set_zero,
                                        user_data="test",
                                    )
                                    dpg.bind_item_theme(
                                        btn_set0_gripper, self.gray_btn_theme
                                    )

                                dpg.add_spacer(height=10, tag=self.rs(h=10))

                                # SPEED SLIDER RESTORED
                                with dpg.table(
                                    header_row=False,
                                    width=470,
                                    borders_innerH=False,
                                    borders_outerH=False,
                                    borders_innerV=False,
                                    borders_outerV=False,
                                    tag=self.rs(w=470),
                                ):
                                    dpg.add_table_column(
                                        width_fixed=True,
                                        init_width_or_weight=90,
                                        width=90,
                                        tag=self.rs(w=90),
                                    )
                                    dpg.add_table_column()
                                    with dpg.table_row():
                                        txt_speed = dpg.add_text(
                                            "Speed: 75%", tag="speed_text_label_control"
                                        )
                                        dpg.bind_item_theme(
                                            txt_speed, self.white_text_theme
                                        )

                                        slider_speed = dpg.add_slider_int(
                                            width=370,
                                            default_value=75,
                                            format="",
                                            tag=self.rs(
                                                370, tag="slider_speed_control"
                                            ),
                                            callback=self.on_speed_change_control,
                                        )
                                        dpg.bind_item_theme(
                                            slider_speed, self.slider_theme
                                        )

                            dpg.add_spacer(width=40, tag=self.rs(w=40))

                            with dpg.group():
                                with dpg.child_window(
                                    width=280, height=165, tag=self.rs(280, 165)
                                ):
                                    dpg.add_spacer(height=16, tag=self.rs(h=16))
                                    axes = ["X", "Y", "Z"]
                                    for axis in axes:
                                        with dpg.group(horizontal=True):
                                            dpg.add_spacer(width=40, tag=self.rs(w=40))
                                            axis_label = dpg.add_text(f"{axis}: ")
                                            dpg.bind_item_theme(
                                                axis_label, self.white_text_theme
                                            )
                                            axis_value = dpg.add_text(
                                                "0.00",
                                                tag=f"coord_{axis.lower()}_control",
                                            )
                                            dpg.bind_item_theme(
                                                axis_value, self.white_text_theme
                                            )
                                        dpg.add_spacer(height=18, tag=self.rs(h=18))

            with dpg.group(tag="page_simulation", show=False):
                dpg.add_spacer(height=30, tag=self.rs(h=30))
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=100, tag=self.rs(w=100))
                    with dpg.group():

                        with dpg.child_window(
                            width=1060, height=80, tag=self.rs(1060, 80)
                        ):
                            dpg.add_spacer(height=20)
                            with dpg.group(horizontal=True):
                                dpg.add_spacer(width=15)
                                self.add_sim_controls("sim")
                                dpg.add_spacer(width=30)
                                with dpg.group():
                                    dpg.add_spacer(height=8)
                                    self.txt_sim_status = dpg.add_text(
                                        "Simulation: Stopped", color=[255, 184, 0]
                                    )
                                dpg.add_spacer(width=40)
                                with dpg.group():
                                    dpg.add_spacer(height=8)
                                    self.txt_sim_pos = dpg.add_text(
                                        "Current position: X=0.000, Y=0.000"
                                    )
                                    dpg.bind_item_theme(
                                        self.txt_sim_pos, self.white_text_theme
                                    )

                        dpg.add_spacer(height=20)

                        with dpg.group(horizontal=True):
                            with dpg.child_window(
                                width=360, height=325, tag=self.rs(360, 325)
                            ):
                                dpg.add_spacer(height=8)
                                dpg.add_text(
                                    "Platform Control", color=[255, 184, 0], indent=15
                                )
                                dpg.add_spacer(height=25)
                                with dpg.group(horizontal=True):
                                    dpg.add_spacer(width=35)
                                    with dpg.group():
                                        with dpg.group(horizontal=True):
                                            btn_q = dpg.add_button(
                                                label="NW [Q]",
                                                width=85,
                                                height=65,
                                                callback=self.on_sim_move,
                                                user_data=(-1, -1),
                                            )
                                            btn_w = dpg.add_button(
                                                label="N [W]",
                                                width=85,
                                                height=65,
                                                callback=self.on_sim_move,
                                                user_data=(0, -1),
                                            )
                                            btn_e = dpg.add_button(
                                                label="NE [E]",
                                                width=85,
                                                height=65,
                                                callback=self.on_sim_move,
                                                user_data=(1, -1),
                                            )
                                        with dpg.group(horizontal=True):
                                            btn_a = dpg.add_button(
                                                label="W [A]",
                                                width=85,
                                                height=65,
                                                callback=self.on_sim_move,
                                                user_data=(-1, 0),
                                            )
                                            btn_c = dpg.add_button(
                                                label="Center [C]",
                                                width=85,
                                                height=65,
                                                callback=self.on_sim_center,
                                            )
                                            btn_d = dpg.add_button(
                                                label="E [D]",
                                                width=85,
                                                height=65,
                                                callback=self.on_sim_move,
                                                user_data=(1, 0),
                                            )
                                        with dpg.group(horizontal=True):
                                            btn_z = dpg.add_button(
                                                label="SW [Z]",
                                                width=85,
                                                height=65,
                                                callback=self.on_sim_move,
                                                user_data=(-1, 1),
                                            )
                                            btn_s = dpg.add_button(
                                                label="S [S]",
                                                width=85,
                                                height=65,
                                                callback=self.on_sim_move,
                                                user_data=(0, 1),
                                            )
                                            btn_x = dpg.add_button(
                                                label="SE [X]",
                                                width=85,
                                                height=65,
                                                callback=self.on_sim_move,
                                                user_data=(1, 1),
                                            )

                                        for btn in [
                                            btn_q,
                                            btn_w,
                                            btn_e,
                                            btn_a,
                                            btn_c,
                                            btn_d,
                                            btn_z,
                                            btn_s,
                                            btn_x,
                                        ]:
                                            dpg.bind_item_theme(
                                                btn, self.gray_btn_theme
                                            )

                            dpg.add_spacer(width=20)

                            with dpg.group():
                                with dpg.child_window(width=664, height=90):
                                    dpg.add_spacer(height=5)
                                    dpg.add_text(
                                        "Z axis", color=[255, 184, 0], indent=10
                                    )
                                    with dpg.group(horizontal=True):
                                        dpg.add_spacer(width=10)
                                        btn_z_up = dpg.add_button(
                                            label="Pick up mouse",
                                            width=300,
                                            height=35,
                                            callback=self.on_sim_z_axis,
                                            user_data=True,
                                        )
                                        btn_z_down = dpg.add_button(
                                            label="Put down mouse",
                                            width=300,
                                            height=35,
                                            callback=self.on_sim_z_axis,
                                            user_data=False,
                                        )
                                        dpg.bind_item_theme(
                                            btn_z_up, self.gray_btn_theme
                                        )
                                        dpg.bind_item_theme(
                                            btn_z_down, self.gray_btn_theme
                                        )

                                dpg.add_spacer(height=20)

                                with dpg.child_window(width=664, height=90):
                                    dpg.add_spacer(height=5)
                                    dpg.add_text(
                                        "Gripper", color=[255, 184, 0], indent=10
                                    )
                                    with dpg.group(horizontal=True):
                                        dpg.add_spacer(width=10)
                                        btn_g_open = dpg.add_button(
                                            label="Gripper open",
                                            width=300,
                                            height=35,
                                            callback=self.on_sim_gripper,
                                            user_data=False,
                                        )
                                        btn_g_close = dpg.add_button(
                                            label="Gripper close",
                                            width=300,
                                            height=35,
                                            callback=self.on_sim_gripper,
                                            user_data=True,
                                        )
                                        dpg.bind_item_theme(
                                            btn_g_open, self.gray_btn_theme
                                        )
                                        dpg.bind_item_theme(
                                            btn_g_close, self.gray_btn_theme
                                        )

                                dpg.add_spacer(height=20)

                                with dpg.child_window(width=664, height=90):
                                    dpg.add_spacer(height=5)
                                    dpg.add_text(
                                        "Mouse Control", color=[255, 184, 0], indent=10
                                    )
                                    with dpg.group(horizontal=True):
                                        dpg.add_spacer(width=10)
                                        btn_m_left = dpg.add_button(
                                            label="Left click",
                                            width=300,
                                            height=35,
                                            callback=self.on_sim_click,
                                            user_data="left",
                                        )
                                        btn_m_right = dpg.add_button(
                                            label="Right click",
                                            width=300,
                                            height=35,
                                            callback=self.on_sim_click,
                                            user_data="right",
                                        )
                                        dpg.bind_item_theme(
                                            btn_m_left, self.gray_btn_theme
                                        )
                                        dpg.bind_item_theme(
                                            btn_m_right, self.gray_btn_theme
                                        )

                        dpg.add_spacer(height=20)

                        with dpg.child_window(width=1060, height=80):
                            dpg.add_spacer(height=20)
                            with dpg.group(horizontal=True):
                                dpg.add_spacer(width=10)
                                dpg.add_text("Set target position", color=[255, 184, 0])
                                dpg.add_spacer(width=30)
                                dpg.add_text("X:", color=[255, 255, 255])
                                self.input_sim_x = dpg.add_input_text(
                                    width=100, default_value="0.00"
                                )
                                dpg.add_spacer(width=20)
                                dpg.add_text("Y:", color=[255, 255, 255])
                                self.input_sim_y = dpg.add_input_text(
                                    width=100, default_value="0.00"
                                )
                                dpg.add_spacer(width=40)
                                btn_go = dpg.add_button(
                                    label="Go and shoot",
                                    width=200,
                                    height=30,
                                    callback=self.on_sim_go,
                                )
                                dpg.bind_item_theme(btn_go, self.gold_btn_theme)

            with dpg.group(tag="page_settings", show=False):
                dpg.add_spacer(height=60, tag=self.rs(h=60))
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=310, tag=self.rs(w=310))

                    with dpg.group():
                        with dpg.child_window(
                            width=600,
                            height=50,
                            no_scrollbar=True,
                            tag=self.rs(600, 50, tag="row_lang"),
                        ) as row_lang:
                            txt_lang = dpg.add_text(
                                "Language",
                                tag=self.rs(pos=[20, 13], tag="txt_lang"),
                                pos=[20, 13],
                            )
                            dpg.bind_item_theme(txt_lang, self.white_text_theme)
                            combo_lang = dpg.add_combo(
                                items=["English", "Polski"],
                                default_value="English",
                                width=180,
                                pos=[400, 13],
                                callback=self.on_language_change,
                                tag=self.rs(w=180, pos=[400, 13]),
                            )
                            dpg.bind_item_theme(combo_lang, self.gold_combo_theme)
                        dpg.bind_item_theme(row_lang, self.settings_row_theme)
                        dpg.add_spacer(height=10, tag=self.rs(h=10))

                        with dpg.child_window(
                            width=600,
                            height=50,
                            no_scrollbar=True,
                            tag=self.rs(600, 50, tag="row_res"),
                        ) as row_res:
                            txt_res = dpg.add_text(
                                "Resolution",
                                tag=self.rs(pos=[20, 13], tag="txt_res"),
                                pos=[20, 13],
                            )
                            dpg.bind_item_theme(txt_res, self.white_text_theme)
                            combo_res = dpg.add_combo(
                                items=["1280x720", "1920x1080"],
                                default_value="1280x720",
                                width=180,
                                pos=[400, 13],
                                callback=self.on_resolution_change,
                                tag=self.rs(w=180, pos=[400, 13]),
                            )
                            dpg.bind_item_theme(combo_res, self.gold_combo_theme)
                        dpg.bind_item_theme(row_res, self.settings_row_theme)
                        dpg.add_spacer(height=10, tag=self.rs(h=10))

                        # FIX: Added an explicit tag, explicit value-setting function, and a refresh button for COM Ports
                        with dpg.child_window(
                            width=600,
                            height=50,
                            no_scrollbar=True,
                            tag=self.rs(600, 50, tag="row_port"),
                        ) as row_port:
                            txt_port = dpg.add_text(
                                "COM Port",
                                tag=self.rs(pos=[20, 13], tag="txt_port"),
                                pos=[20, 13],
                            )
                            dpg.bind_item_theme(txt_port, self.white_text_theme)

                            combo_port = dpg.add_combo(
                                items=[],
                                width=150,
                                pos=[350, 13],
                                callback=self.on_port_change,
                                tag=self.rs(w=150, pos=[350, 13], tag="combo_port"),
                            )
                            dpg.bind_item_theme(combo_port, self.gold_combo_theme)

                            btn_refresh = dpg.add_button(
                                label="Refresh",
                                width=75,
                                pos=[505, 13],
                                callback=self.refresh_ports,
                                tag=self.rs(
                                    w=75, pos=[505, 13], tag="btn_refresh_ports"
                                ),
                            )
                            dpg.bind_item_theme(btn_refresh, self.gray_btn_theme)

                        dpg.bind_item_theme(row_port, self.settings_row_theme)
                        dpg.add_spacer(height=10, tag=self.rs(h=10))

                        for i in range(5):
                            with dpg.child_window(
                                width=600,
                                height=50,
                                no_scrollbar=True,
                                tag=self.rs(600, 50),
                            ) as row_empty:
                                pass
                            dpg.bind_item_theme(row_empty, self.settings_row_theme)
                            dpg.add_spacer(height=10, tag=self.rs(h=10))

            with dpg.group(tag="page_stat", show=False):
                dpg.add_spacer(height=35, tag=self.rs(h=35))

                card_data = [
                    ("lmb", "tex_stat_lmb"),
                    ("rmb", "tex_stat_rmb"),
                    ("time", "tex_stat_time"),
                    ("mouse", "tex_stat_mouse"),
                    ("dist", "tex_stat_dist"),
                    ("energy", "tex_stat_energy"),
                    ("unknown", ""),
                    ("keys", "tex_stat_keys"),
                ]

                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=90, tag=self.rs(w=90))
                    with dpg.group():
                        for row in range(2):
                            with dpg.group(horizontal=True):
                                for col in range(4):
                                    idx = row * 4 + col
                                    c_id, c_tex = card_data[idx]
                                    with dpg.child_window(
                                        width=255, height=295, tag=self.rs(255, 295)
                                    ) as card_win:
                                        dpg.add_spacer(height=5, tag=self.rs(h=5))
                                        if c_tex:
                                            with dpg.group(horizontal=True):
                                                dpg.add_spacer(
                                                    width=72, tag=self.rs(w=72)
                                                )
                                                dpg.add_image(
                                                    c_tex,
                                                    width=80,
                                                    height=80,
                                                    tag=self.rs(80, 80),
                                                )
                                        else:
                                            dpg.add_spacer(height=80, tag=self.rs(h=80))

                                        dpg.add_spacer(height=15, tag=self.rs(h=15))

                                        title_txt = dpg.add_text(
                                            "", tag=f"stat_title_{c_id}"
                                        )
                                        dpg.bind_item_theme(
                                            title_txt, self.white_text_theme
                                        )

                                        dpg.add_spacer(height=2, tag=self.rs(h=2))
                                        desc_txt = dpg.add_text(
                                            "",
                                            tag=self.rs(
                                                wrap=225, tag=f"stat_desc_{c_id}"
                                            ),
                                            wrap=225,
                                        )
                                        dpg.bind_item_theme(
                                            desc_txt, self.gold_text_theme
                                        )

                                        dpg.add_spacer(height=20, tag=self.rs(h=20))

                                        val_btn = dpg.add_button(
                                            label=StatsManager.format_value(
                                                c_id, self.stats_manager.get(c_id)
                                            ),
                                            width=225,
                                            height=45,
                                            tag=self.rs(
                                                225, 45, tag=f"stat_val_{c_id}"
                                            ),
                                        )
                                        dpg.bind_item_theme(
                                            val_btn, self.stat_value_theme
                                        )

                                    dpg.bind_item_theme(card_win, self.stat_card_theme)
                                    if col < 3:
                                        dpg.add_spacer(width=20, tag=self.rs(w=20))
                            if row == 0:
                                dpg.add_spacer(height=20, tag=self.rs(h=20))
        with dpg.window(
            tag=self.rs(self.width, self.height, tag="window_dim"),
            width=self.width,
            height=self.height,
            pos=(0, 0),
            no_title_bar=True,
            no_resize=True,
            no_move=True,
            show=False,
        ):
            dpg.bind_item_theme("window_dim", self.dim_theme)
            dpg.add_button(
                width=self.width,
                height=self.height,
                callback=self.toggle_sidebar,
                tag=self.rs(1280, 720),
            )
            dpg.bind_item_theme(dpg.last_item(), self.invisible_btn_theme)

        with dpg.window(
            tag=self.rs(60, self.height, tag="window_sidebar"),
            width=60,
            height=self.height,
            pos=(0, 0),
            no_title_bar=True,
            no_resize=True,
            no_move=True,
        ):
            dpg.bind_item_theme("window_sidebar", self.sidebar_theme)
            with dpg.child_window(
                tag=self.rs(60, self.height, tag="sidebar_child"),
                width=60,
                height=self.height,
                border=False,
                no_scrollbar=True,
            ):
                self.nav_texts = []
                with dpg.group(horizontal=True):
                    self.btn_toggle = dpg.add_image_button(
                        texture_tag="tex_menu",
                        width=50,
                        height=50,
                        callback=self.toggle_sidebar,
                        tag=self.rs(50, 50),
                    )
                    dpg.bind_item_theme(self.btn_toggle, self.transparent_btn_theme)
                    with dpg.group():
                        dpg.add_spacer(height=15, tag=self.rs(h=15))
                        self.title_text = dpg.add_text("CSAimBot 1.0", show=False)
                        dpg.bind_item_theme(self.title_text, self.white_text_theme)

                dpg.add_spacer(height=20, tag=self.rs(h=20))
                self.nav_texts = []
                for page_tag, item_config in self.nav_config.items():
                    btn_tag = f"nav_btn_{page_tag}"
                    text_tag = f"nav_text_{page_tag}"
                    self.nav_elements[page_tag] = {"btn": btn_tag, "text": text_tag}

                    with dpg.group(horizontal=True):
                        btn = dpg.add_image_button(
                            texture_tag=item_config["inactive_tex"],
                            width=50,
                            height=50,
                            callback=self.switch_page,
                            user_data=page_tag,
                            tag=self.rs(50, 50, tag=btn_tag),
                        )
                        dpg.bind_item_theme(btn, self.transparent_btn_theme)

                        with dpg.group():
                            dpg.add_spacer(height=15, tag=self.rs(h=15))
                            txt = dpg.add_text(
                                item_config["label"], show=False, tag=text_tag
                            )
                            dpg.bind_item_theme(txt, self.gray_text_theme)

                            with dpg.item_handler_registry() as text_click_handler:
                                dpg.add_item_clicked_handler(
                                    button=0,
                                    callback=self.switch_page,
                                    user_data=page_tag,
                                )
                            dpg.bind_item_handler_registry(txt, text_click_handler)

                        self.nav_texts.append(txt)
                    dpg.add_spacer(height=5, tag=self.rs(h=5))

                dpg.add_spacer(height=150, tag=self.rs(h=150))

                with dpg.group(tag="group_conn_text_placeholder", show=True):
                    dpg.add_spacer(height=32, tag=self.rs(h=32))

                with dpg.group(tag="group_conn_text", show=False):
                    with dpg.group(horizontal=True):
                        dpg.add_spacer(width=10, tag=self.rs(w=10))
                        color = [80, 255, 80] if self.is_connected else [255, 80, 80]
                        text_val = (
                            "Status: OK"
                            if self.is_connected
                            else f"Error: {self.connection_msg}"
                        )
                        self.conn_text = dpg.add_text(text_val, color=color)
                    dpg.add_spacer(height=5, tag=self.rs(h=5))

                tex_icon = "tex_conn_green" if self.is_connected else "tex_conn_red"
                tex_full = (
                    "tex_conn_green_full" if self.is_connected else "tex_conn_red_full"
                )

                with dpg.group(horizontal=True, tag="group_conn_icon", show=True):
                    self.btn_connect_icon = dpg.add_image_button(
                        texture_tag=tex_icon,
                        width=50,
                        height=50,
                        indent=2,
                        callback=self.on_connect_click,
                        tag=self.rs(50, 50),
                    )
                    dpg.bind_item_theme(
                        self.btn_connect_icon, self.transparent_btn_theme
                    )

                with dpg.group(horizontal=True, tag="group_conn_full", show=False):
                    self.btn_connect_full = dpg.add_image_button(
                        texture_tag=tex_full,
                        width=220,
                        height=50,
                        indent=2,
                        callback=self.on_connect_click,
                        tag=self.rs(220, 50),
                    )
                    dpg.bind_item_theme(
                        self.btn_connect_full, self.transparent_btn_theme
                    )

    def on_speed_change_control(self, app_data):
        """Update the active speed setting."""
        self.current_speed = int(app_data)
        t = self.lang_dict[self.current_lang]
        dpg.set_value(
            "speed_text_label_control", f"{t['speed']}: {self.current_speed}%"
        )

    def on_target_change(self, app_data):
        """Update target prioritization across the UI.

        Args:
            app_data: Selected target mode.
        """
        target_tags = ["rbtn_target_home", "rbtn_target_control"]
        for tag in target_tags:
            if dpg.does_item_exist(tag):
                # Force the new value onto the widget
                dpg.set_value(tag, app_data)

                # Dynamically update the theme based on current selection
                if app_data == "TT":
                    dpg.bind_item_theme(tag, self.yellow_rbtn_theme)
                elif app_data == "CT":
                    dpg.bind_item_theme(tag, self.blue_rbtn_theme)
                else:
                    dpg.bind_item_theme(tag, self.violet_rbtn_theme)

        # Send the updated target mode to the vision worker process
        self.pipe.send({"cmd": "SET_TARGET", "value": app_data})

    def on_debug_toggle(self, sender, app_data):
        """Toggle the OpenCV debug preview.

        Args:
            app_data: Checkbox state.
        """
        for tag in ["chk_debug_home", "chk_debug_control"]:
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, app_data)

        self.pipe.send({"cmd": "DEBUG", "value": app_data})

    def add_log(self, text, color=[255, 255, 255], parent=None):
        """Append a log line to the available log panel.

        Args:
            text: Log message text.
            color: Text color for the log line.
            parent: Optional parent group tag.
        """
        if parent:
            if dpg.does_item_exist(parent):
                dpg.add_text(text, parent=parent, color=color)
        else:
            for group in ["logs_group_control", "logs_group_home"]:
                if dpg.does_item_exist(group):
                    dpg.add_text(text, parent=group, color=color)

    def refresh_stats_display(self):
        """Reload stats from storage and update the statistic cards."""
        self.stats_manager.reload()
        for key in StatsManager.DEFAULTS:
            tag = f"stat_val_{key}"
            if dpg.does_item_exist(tag):
                dpg.configure_item(
                    tag,
                    label=StatsManager.format_value(key, self.stats_manager.get(key)),
                )

    def on_port_change(self, sender, app_data):
        """Request a serial port change.

        Args:
            app_data: Selected COM port.
        """
        self.connection_state = "connecting"
        self.update_connection_display()
        self.comms_pipe.send({"cmd": "CHANGE_PORT", "value": app_data})

    def on_connect_click(self, sender, app_data):
        """Connect or disconnect from the ESP32 depending on current state."""
        if not self.is_connected:
            self.connection_state = "connecting"
            self.update_connection_display()
            self.comms_pipe.send({"cmd": "CONNECT"})
        else:
            self.connection_state = "disconnecting"
            self.update_connection_display()
            self.comms_pipe.send({"cmd": "DISCONNECT"})

    def on_step_adjust(self, sender, app_data, user_data):
        """Adjust the simulated step position for a control action.

        Args:
            user_data: Tuple of action key and direction.
        """
        action_key, direction = user_data
        step = 10 * direction
        simulated_key = ""

        if action_key == "lmb":  # X-axis
            self.pos_x += step
            simulated_key = "l" if direction > 0 else "j"
        elif action_key == "rmb":  # Y-axis
            self.pos_y += step
            simulated_key = "i" if direction > 0 else "k"
        elif action_key == "gripper":  # Z-axis
            self.pos_z += step
            simulated_key = "z" if direction > 0 else "x"

        self._update_coords_display()

        if self.is_connected:
            self.comms_pipe.send(
                {
                    "cmd": "SEND",
                    "value": f"{self.pos_x},{self.pos_y},{self.current_speed},{simulated_key}",
                }
            )

    def on_set_zero(self, sender, app_data, user_data):
        """Reset the selected control axis to zero.

        Args:
            user_data: Action key identifying which axis to reset.
        """
        if user_data == "lmb":
            self.pos_x = 0
        elif user_data == "rmb":
            self.pos_y = 0
        elif user_data == "gripper":
            self.pos_z = 0

        self._update_coords_display()

        if self.is_connected:
            self.comms_pipe.send({"cmd": "SEND", "value": f"0,0,{self.current_speed},"})

    def _update_coords_display(self):
        """Refresh all coordinate readouts in the UI with 2-decimal formatting."""
        formatted_x = f"{self.pos_x:.2f}"
        formatted_y = f"{self.pos_y:.2f}"
        formatted_z = f"{self.pos_z:.2f}"

        for tag_x in ["coord_x_control", "coord_x_home"]:
            if dpg.does_item_exist(tag_x):
                dpg.set_value(tag_x, formatted_x)
        for tag_y in ["coord_y_control", "coord_y_home"]:
            if dpg.does_item_exist(tag_y):
                dpg.set_value(tag_y, formatted_y)
        for tag_z in ["coord_z_control", "coord_z_home"]:
            if dpg.does_item_exist(tag_z):
                dpg.set_value(tag_z, formatted_z)

    def on_start(self):
        """Start the vision worker and activate mouse blocker."""
        self.pipe.send({"cmd": "START"})
        if self.mouse_blocker_pipe:
            self.mouse_blocker_pipe.send({"cmd": "START"})

    def on_stop(self):
        """Stop the vision worker, deactivate mouse blocker, and emergency-stop the controller."""
        self.pipe.send({"cmd": "STOP"})
        if self.mouse_blocker_pipe:
            self.mouse_blocker_pipe.send({"cmd": "STOP"})
        if self.is_connected:
            self.comms_pipe.send(
                {"cmd": "SEND", "value": f"0,0,{self.current_speed},p"}
            )
            self.add_log("<System> EMERGENCY STOP ACTIVATED", color=[255, 0, 0])

    def on_calibrate(self):
        """Start calibration in the vision worker."""
        self.pipe.send({"cmd": "CALIBRATE"})

    def on_start_sim(self):
        """Request simulation start."""
        self.simulation_state = "starting"
        self.sim_pipe.send({"cmd": "START_SIM"})
        self.update_simulation_display()

    def on_stop_sim(self, sender, app_data):
        """Request simulation stop."""
        self.simulation_state = "stopping"
        self.sim_pipe.send({"cmd": "STOP_SIM"})
        self.update_simulation_display()

    def update_simulation_display(self):
        """Enable or disable simulation controls based on current state."""
        is_running = self.simulation_state == "running"
        is_pending = self.simulation_state in ("starting", "stopping")

        for suffix in ["sim"]:
            start_tag = f"btn_start_sim_{suffix}"
            stop_tag = f"btn_stop_sim_{suffix}"

            if dpg.does_item_exist(start_tag):
                dpg.configure_item(start_tag, enabled=not is_running and not is_pending)
            if dpg.does_item_exist(stop_tag):
                dpg.configure_item(stop_tag, enabled=is_running and not is_pending)

    def poll_pipe(self):
        """Process messages from the worker processes.

        Important protocol rule:
        - Vision offsets from aimbot.py are stored in target_offset_x/y.
        - Manual keys are sent with 0,0 offset so old AI offsets cannot mix with jog commands.
        - If no manual key is active, each valid vision offset is forwarded to ESP32 as AIM input.
        """
        last_vision_send = 0

        while self.running:
            # =================================================================
            # 1. VISION PIPE - Drain and send the latest YOLO data
            # =================================================================
            latest_vision_msg = None

            while self.pipe.poll():
                msg = self.pipe.recv()
                if msg.get("type") == "offsets":
                    latest_vision_msg = msg

            if latest_vision_msg:
                x_val = latest_vision_msg.get("x")
                y_val = latest_vision_msg.get("y")

                force_update = False

                if x_val is None or y_val is None or x_val == "-" or y_val == "-":
                    if self.target_offset_x != 0 or self.target_offset_y != 0:
                        force_update = True
                    self.target_offset_x = 0
                    self.target_offset_y = 0
                else:
                    try:
                        self.target_offset_x = int(x_val)
                        self.target_offset_y = -int(y_val)
                    except (TypeError, ValueError):
                        self.target_offset_x = 0
                        self.target_offset_y = 0

                now = time.time()
                if self.is_connected and not self.manual_keys:
                    if force_update or (now - last_vision_send > 0.05):

                        dist = math.hypot(self.target_offset_x, self.target_offset_y)

                        # =====================================================
                        # NON-LINEAR PROPORTIONAL CONTROLLER (Aggressive brake)
                        # =====================================================
                        slowdown_radius = (
                            350.0  # Pixels distance to start hitting the brakes
                        )

                        if dist > slowdown_radius:
                            dyn_speed = self.current_speed
                        else:
                            # Exponential deceleration using a power of 1.5
                            # The closer the bot gets, the harder it brakes
                            scale = (dist / slowdown_radius) ** 1.5
                            dyn_speed = int(2 + (self.current_speed - 2) * scale)

                        # Safety clamp
                        dyn_speed = max(2, min(dyn_speed, self.current_speed))

                        # Hard stop if within ESP32 deadzone
                        if dist <= 15:
                            dyn_speed = 0

                        # DEBUG: Print real-time dynamic speed to the console
                        if dist > 0:
                            print(
                                f"<AIMBOT> Dist: {dist:.0f}px | Speed sent: {dyn_speed}%",
                                flush=True,
                            )

                        self.comms_pipe.send(
                            {
                                "cmd": "SEND",
                                "value": f"{self.target_offset_x},{self.target_offset_y},{dyn_speed},",
                            }
                        )
                        last_vision_send = now

            # =================================================================
            # 2. COMMS PIPE - Receive logs from ESP32 and physical keyboard
            # =================================================================
            while self.comms_pipe.poll():
                msg = self.comms_pipe.recv()
                if msg.get("type") == "connection_status":
                    self.connection_state = msg.get("status")
                    self.is_connected = self.connection_state == "connected"
                    self.update_connection_display()
                elif msg.get("type") == "keyboard":
                    keys = msg.get("keys") or ""
                    self.manual_keys = keys

                    if self.is_connected:
                        if keys:
                            self.comms_pipe.send(
                                {
                                    "cmd": "SEND",
                                    "value": f"0,0,{self.current_speed},{keys}",
                                }
                            )
                        else:
                            self.comms_pipe.send(
                                {
                                    "cmd": "SEND",
                                    "value": f"{self.target_offset_x},{self.target_offset_y},{self.current_speed},",
                                }
                            )

                    display_text = f"[ {keys.upper()} ]" if keys else "[ BRAK ]"
                    if dpg.does_item_exist("current_keys_text"):
                        dpg.set_value("current_keys_text", display_text)
                elif msg.get("type") == "esp_msg":
                    esp_text = msg.get("value")
                    print(f"<ESP32> {esp_text}", flush=True)
                    # PARSING LOGIC: Extract X and Y values from the ESP32 status string
                    # Example format: "E1: 100 | E2: 200 | X: 12.34 | Y: 5.67 | ..."
                    try:
                        if "X:" in esp_text and "Y:" in esp_text:
                            parts = esp_text.split("|")
                            for part in parts:
                                part = part.strip()
                                if part.startswith("X:"):
                                    # Extract number after "X: "
                                    self.pos_x = float(part.split(":")[1].strip())
                                elif part.startswith("Y:"):
                                    # Extract number after "Y: "
                                    self.pos_y = float(part.split(":")[1].strip())

                            # Push the newly parsed physical coordinates to the UI
                            self._update_coords_display()
                    except (ValueError, IndexError) as e:
                        # Silently ignore parsing errors from incomplete serial strings
                        pass
                elif msg.get("type") == "stat_update":
                    key, value = msg.get("key"), msg.get("value")
                    if key and value is not None:
                        self.stats_manager.set(key, value)
                        tag = f"stat_val_{key}"
                        if dpg.does_item_exist(tag):
                            dpg.configure_item(
                                tag, label=StatsManager.format_value(key, value)
                            )
                elif msg.get("type") == "stat_increment":
                    key = msg.get("key")
                    amount = msg.get("amount", 1)
                    if key:
                        self.stats_manager.increment(key, amount)
                        tag = f"stat_val_{key}"
                        if dpg.does_item_exist(tag):
                            dpg.configure_item(
                                tag,
                                label=StatsManager.format_value(
                                    key, self.stats_manager.get(key)
                                ),
                            )

            # =================================================================
            # 3. SIM PIPE - Receive side simulation status
            # =================================================================
            while self.sim_pipe.poll():
                msg = self.sim_pipe.recv()
                if msg.get("type") == "simulation_status":
                    self.simulation_state = msg.get("status", "stopped")
                    message = msg.get("message")
                    if message:
                        color = (
                            [80, 255, 80]
                            if self.simulation_state == "running"
                            else [255, 255, 80]
                        )
                        if "error" in message.lower() or "not found" in message.lower():
                            color = [255, 80, 80]
                        self.add_log(message, color)
                        if hasattr(self, "txt_sim_status") and dpg.does_item_exist(
                            self.txt_sim_status
                        ):
                            dpg.set_value(self.txt_sim_status, f"Simulation: {message}")
                            dpg.configure_item(self.txt_sim_status, color=color)
                    self.update_simulation_display()
                elif msg.get("type") == "sim_position_updated":
                    if hasattr(self, "txt_sim_pos") and dpg.does_item_exist(
                        self.txt_sim_pos
                    ):
                        x, y = msg.get("x", 0.0), msg.get("y", 0.0)
                        dpg.set_value(
                            self.txt_sim_pos, f"Current position: X={x:.4f}, Y={y:.4f}"
                        )

            time.sleep(0.01)

            now = time.time()
            if now - self._last_stats_refresh >= 5:
                self._last_stats_refresh = now
                self.refresh_stats_display()

    def run(self):
        """Show the viewport and enter the main UI loop."""
        dpg.set_primary_window("window_root", True)
        dpg.show_viewport()

        last_sent_key = ""

        while dpg.is_dearpygui_running():
            current_key = ""

            # X-Axis Jogging (LMB row)
            if dpg.does_item_exist("btn_left_lmb") and dpg.is_item_active(
                "btn_left_lmb"
            ):
                current_key = "j"
            elif dpg.does_item_exist("btn_right_lmb") and dpg.is_item_active(
                "btn_right_lmb"
            ):
                current_key = "l"

            # Y-Axis Jogging (RMB row)
            elif dpg.does_item_exist("btn_left_rmb") and dpg.is_item_active(
                "btn_left_rmb"
            ):
                current_key = "k"
            elif dpg.does_item_exist("btn_right_rmb") and dpg.is_item_active(
                "btn_right_rmb"
            ):
                current_key = "i"

            # Z-Axis Jogging (Gripper row)
            elif dpg.does_item_exist("btn_left_gripper") and dpg.is_item_active(
                "btn_left_gripper"
            ):
                current_key = "x"
            elif dpg.does_item_exist("btn_right_gripper") and dpg.is_item_active(
                "btn_right_gripper"
            ):
                current_key = "z"

            # Main action buttons (Relays & Servo)
            elif dpg.does_item_exist("btn_lmb_control") and dpg.is_item_active(
                "btn_lmb_control"
            ):
                current_key = "1"
            elif dpg.does_item_exist("btn_rmb_control") and dpg.is_item_active(
                "btn_rmb_control"
            ):
                current_key = "2"
            elif dpg.does_item_exist("btn_gripper_control") and dpg.is_item_active(
                "btn_gripper_control"
            ):
                current_key = "v"
            elif dpg.does_item_exist("btn_homing_control") and dpg.is_item_active(
                "btn_homing_control"
            ):
                current_key = "h"
            elif dpg.does_item_exist("btn_centering_control") and dpg.is_item_active(
                "btn_centering_control"
            ):
                current_key = "c"

            if not current_key:
                # Keyboard input is already forwarded by comms_worker
                pass

            if current_key != last_sent_key:
                if self.is_connected:
                    self.comms_pipe.send(
                        {
                            "cmd": "SEND",
                            "value": f"0,0,{self.current_speed},{current_key}",
                        }
                    )
                last_sent_key = current_key

            for page_tag, elements in self.nav_elements.items():
                config = self.nav_config.get(page_tag)
                if dpg.does_item_exist(elements["btn"]) and dpg.does_item_exist(
                    elements["text"]
                ):
                    if page_tag == self.active_page_tag:
                        dpg.configure_item(
                            elements["btn"], texture_tag=config["active_tex"] #type: ignore
                        )
                    else:
                        dpg.configure_item(
                            elements["btn"], texture_tag=config["inactive_tex"] #type: ignore
                        )

            dpg.render_dearpygui_frame()

        self.running = False
        self.pipe.send({"cmd": "QUIT"})
        self.comms_pipe.send({"cmd": "QUIT"})
        self.sim_pipe.send({"cmd": "QUIT"})
        dpg.destroy_context()


if __name__ == "__main__":
    print(
        "This module is not meant to be run directly. Please run the main application instead."
    )
