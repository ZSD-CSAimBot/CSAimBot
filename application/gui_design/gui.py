import math
import threading
import os
import multiprocessing
import random
import dearpygui.dearpygui as dpg
import time
import serial.tools.list_ports


class GUI:
    def __init__(self, vision_pipe, comms_pipe):
        self.pipe = vision_pipe  # Pipe do obrazu/YOLO
        self.comms_pipe = comms_pipe  # Pipe do modułu ESP i klawiatury
        self.running = True
        self.sidebar_expanded = False

        self.is_connected = False
        self.connection_msg = "Connected to ESP32" if self.is_connected else "No connection to ESP32"
        self.connection_state = "disconnected"

        self.active_page_tag = "page_home"
        self.nav_config = {
            "page_home": {"label": "Home Page", "active_tex": "tex_home", "inactive_tex": "tex_home_inactive"},
            "page_control": {"label": "Control Panel", "active_tex": "tex_control",
                             "inactive_tex": "tex_control_inactive"},
            "page_stat": {"label": "Statistics", "active_tex": "tex_stat", "inactive_tex": "tex_stat_inactive"},
            "page_settings": {"label": "Settings", "active_tex": "tex_settings",
                              "inactive_tex": "tex_settings_inactive"}
        }
        self.nav_elements = {}
        self.current_lang = "English"
        self.lang_dict = {
            "English": {
                "nav_home": "Home Page", "nav_control": "Control Panel", "nav_stat": "Statistics",
                "nav_settings": "Settings",
                "start": "START", "cal": "CALIBRATE", "stop": "FORCE STOP",
                "lang": "Language", "res": "Resolution", "port": "COM Port", "status_ok": "Status: OK","status_err": "Error: ",
                "target": "Target Prioritization:", "logs": "System Logs:", "opencv": "Show OpenCV window",
                "lpm": "Press LMB", "ppm": "Press RMB", "test": "Gripper Test", "set0": "Set 0",
                "plot_data": "Data", "plot_vision": "Vision Data", "speed": "Speed",
                "stat_lmb_title": "LMB Clicked",
                "stat_lmb_desc": "How many times has the bot clicked left mouse button",
                "stat_rmb_title": "RMB Clicked",
                "stat_rmb_desc": "How many times has the bot clicked right mouse button",
                "stat_time_title": "Time ON",
                "stat_time_desc": "Amount time while the bot has been connected and turned on",
                "stat_mouse_title": "Mouses calibrated", "stat_mouse_desc": "Amount of mouses calibrated by the bot",
                "stat_dist_title": "Distance Traveled", "stat_dist_desc": "Total distance traveled by a mouse",
                "stat_energy_title": "Energy wasted",
                "stat_energy_desc": "Aproximated amount of energy used by the bot",
                "stat_unknown_title": "???", "stat_unknown_desc": "???",
                "stat_keys_title": "Keys pressed", "stat_keys_desc": "Amount of key presses by a user"
            },
            "Polski": {
                "nav_home": "Strona Główna", "nav_control": "Panel Sterowania", "nav_stat": "Statystyki",
                "nav_settings": "Ustawienia",
                "start": "START", "cal": "KALIBRUJ", "stop": "WYMUŚ STOP",
                "lang": "Język", "res": "Rozdzielczość", "port": "Port COM", "status_ok": "Status: OK", "status_err": "Błąd: ",
                "target": "Priorytet Celu:", "logs": "Logi Systemowe:", "opencv": "Pokaż okno OpenCV",
                "lpm": "Wciśnij LPM", "ppm": "Wciśnij PPM", "test": "Test Chwytaka", "set0": "Ustaw 0",
                "plot_data": "Dane", "plot_vision": "Dane Wizyjne", "speed": "Prędkość",
                "stat_lmb_title": "Kliknięcia LPM", "stat_lmb_desc": "Ile razy bot kliknął lewy przycisk myszy",
                "stat_rmb_title": "Kliknięcia PPM", "stat_rmb_desc": "Ile razy bot kliknął prawy przycisk myszy",
                "stat_time_title": "Czas działania", "stat_time_desc": "Czas, przez który bot był połączony i włączony",
                "stat_mouse_title": "Skalibrowane myszy", "stat_mouse_desc": "Ilość myszy skalibrowanych przez bota",
                "stat_dist_title": "Przebyty dystans", "stat_dist_desc": "Całkowity dystans przebyty przez mysz",
                "stat_energy_title": "Zużyta energia",
                "stat_energy_desc": "Przybliżona ilość energii zużytej przez bota",
                "stat_unknown_title": "???", "stat_unknown_desc": "???",
                "stat_keys_title": "Wciśnięte klawisze",
                "stat_keys_desc": "Ilość klawiszy wciśniętych przez użytkownika"
            }
        }
        dpg.create_context()
        self.width = 1280
        self.height = 720
        dpg.create_viewport(title='CSAimBot Control Panel', width=self.width, height=self.height, resizable=False)
        dpg.setup_dearpygui()

        self.setup_fonts()
        self.setup_themes()
        self.load_textures()
        self.build_ui()

        self.listener_thread = threading.Thread(target=self.poll_pipe, daemon=True)
        self.listener_thread.start()

        self.on_language_change(None, "English")

    def switch_page(self, sender, app_data, user_data):
        pages = ["page_home", "page_control", "page_stat", "page_settings"]
        for page in pages:
            if dpg.does_item_exist(page):
                dpg.configure_item(page, show=(page == user_data))

        self.active_page_tag = user_data

        if self.sidebar_expanded:
            self.toggle_sidebar(None, None)

    def setup_fonts(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(current_dir, "fonts", "Roboto.ttf")

        with dpg.font_registry():
            if os.path.exists(font_path):
                with dpg.font(font_path, 17) as self.default_font:
                    dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                    dpg.add_font_range(0x0100, 0x017F)
                dpg.bind_font(self.default_font)

    def create_rbtn_theme(self, bg_color, hover_color, dot_color, text_color):
        with dpg.theme() as theme_id:
            with dpg.theme_component(dpg.mvRadioButton):
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, bg_color)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, hover_color)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, bg_color)
                dpg.add_theme_color(dpg.mvThemeCol_CheckMark, dot_color)
                dpg.add_theme_color(dpg.mvThemeCol_Text, text_color)
        return theme_id

    def setup_themes(self):
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

        self.gray_btn_theme = self.create_btn_theme([54, 60, 70], [70, 70, 70], [30, 30, 30])
        self.green_btn_theme = self.create_btn_theme([50, 200, 50], [70, 255, 70], [30, 150, 30])
        self.red_btn_theme = self.create_btn_theme([200, 0, 0], [220, 0, 0], [180, 0, 0])
        self.gold_btn_theme = self.create_btn_theme([255, 190, 25], [255, 200, 0], [255, 160, 0], [40, 40, 60])
        self.transparent_btn_theme = self.create_btn_theme([0, 0, 0, 0], [255, 255, 255, 20], [255, 255, 255, 40])

        self.yellow_rbtn_theme = self.create_rbtn_theme([50, 50, 0], [70, 70, 0], [255, 255, 0], [255, 255, 255])
        self.blue_rbtn_theme = self.create_rbtn_theme([0, 0, 50], [0, 0, 70], [0, 255, 255], [255, 255, 255])
        self.violet_rbtn_theme = self.create_rbtn_theme([50, 0, 50], [70, 0, 70], [255, 0, 255], [255, 255, 255])

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

        self.invisible_btn_theme = self.create_btn_theme([0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0])

    def create_btn_theme(self, color, hover_color, active_color, text_color=[255, 255, 255]):
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
        current_dir = os.path.dirname(os.path.abspath(__file__))

        with dpg.texture_registry(show=False):
            def load_and_add(rel_path, tag):
                path_parts = rel_path.split("/")
                full_path = os.path.join(current_dir, *path_parts)
                try:
                    img = dpg.load_image(full_path)
                    if img:
                        dpg.add_static_texture(width=img[0], height=img[1], default_value=img[3], tag=tag)
                    else:
                        dpg.add_static_texture(width=1, height=1, default_value=[0.0, 0.0, 0.0, 0.0], tag=tag)
                except Exception:
                    dpg.add_static_texture(width=1, height=1, default_value=[0.0, 0.0, 0.0, 0.0], tag=tag)

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
            load_and_add("icons/connect/ikona_connect_red_full.png", "tex_conn_red_full")
            load_and_add("icons/connect/ikona_connect_green.png", "tex_conn_green")
            load_and_add("icons/connect/ikona_connect_green_full.png", "tex_conn_green_full")
            load_and_add("icons/connect/ikona_connect_yellow.png", "tex_conn_yellow")
            load_and_add("icons/connect/ikona_connect_yellow_full1.png", "tex_conn_yellow_full1")
            load_and_add("icons/connect/ikona_connect_yellow_full2.png", "tex_conn_yellow_full2")
            load_and_add("icons/stats/ikona_lmb.png", "tex_stat_lmb")
            load_and_add("icons/stats/ikona_rmb.png", "tex_stat_rmb")
            load_and_add("icons/stats/ikona_time.png", "tex_stat_time")
            load_and_add("icons/stats/ikona_mouse.png", "tex_stat_mouse")
            load_and_add("icons/stats/ikona_dist.png", "tex_stat_dist")
            load_and_add("icons/stats/ikona_energy.png", "tex_stat_energy")
            load_and_add("icons/stats/ikona_keys.png", "tex_stat_keys")


    def toggle_sidebar(self, sender, app_data):
        self.sidebar_expanded = not self.sidebar_expanded
        new_width = 235 if self.sidebar_expanded else 60
        dpg.configure_item("window_sidebar", width=new_width)
        dpg.configure_item("sidebar_child", width=new_width)
        dpg.configure_item("window_dim", show=self.sidebar_expanded)

        if self.sidebar_expanded:
            dpg.focus_item("window_sidebar")

        if dpg.does_alias_exist("tex_menu") and dpg.does_alias_exist("tex_x"):
            dpg.configure_item(self.btn_toggle, texture_tag="tex_x" if self.sidebar_expanded else "tex_menu")

        dpg.configure_item(self.title_text, show=self.sidebar_expanded)
        for txt in self.nav_texts:
            dpg.configure_item(txt, show=self.sidebar_expanded)

        if dpg.does_alias_exist("group_conn_icon") and dpg.does_alias_exist("group_conn_full"):
            dpg.configure_item("group_conn_icon", show=not self.sidebar_expanded)
            dpg.configure_item("group_conn_full", show=self.sidebar_expanded)
            dpg.configure_item("group_conn_text", show=self.sidebar_expanded)
            dpg.configure_item("group_conn_text_placeholder", show=not self.sidebar_expanded)

    def add_nav_item(self, icon_or_texture_tag, text_label, page_tag):
        with dpg.group(horizontal=True):
            if dpg.does_alias_exist(icon_or_texture_tag):
                btn = dpg.add_image_button(texture_tag=icon_or_texture_tag, width=50, height=50,
                                           callback=self.switch_page, user_data=page_tag)
            else:
                btn = dpg.add_button(label=icon_or_texture_tag, width=50, height=50, callback=self.switch_page,
                                     user_data=page_tag)

            dpg.bind_item_theme(btn, self.transparent_btn_theme)
            with dpg.group():
                dpg.add_spacer(height=15)
                txt = dpg.add_text(text_label, show=False)
                dpg.bind_item_theme(txt, self.gold_text_theme)
            self.nav_texts.append(txt)
        dpg.add_spacer(height=5)

    def on_language_change(self, sender, app_data):
        self.current_lang = app_data
        t = self.lang_dict[self.current_lang]

        # Tłumaczenie Paska Nawigacji
        nav_mapping = {"page_home": "nav_home", "page_control": "nav_control", "page_stat": "nav_stat",
                       "page_settings": "nav_settings"}
        for page_tag, dict_key in nav_mapping.items():
            tag = f"nav_text_{page_tag}"
            if dpg.does_item_exist(tag):
                # Do aktualizacji dpg.add_text używamy set_value zamiast configure_item
                dpg.set_value(tag, t[dict_key])

        stat_ids = ["lmb", "rmb", "time", "mouse", "dist", "energy", "unknown", "keys"]
        for s_id in stat_ids:
            title_tag = f"stat_title_{s_id}"
            desc_tag = f"stat_desc_{s_id}"
            if dpg.does_item_exist(title_tag):
                dpg.set_value(title_tag, t[f"stat_{s_id}_title"])
            if dpg.does_item_exist(desc_tag):
                dpg.set_value(desc_tag, t[f"stat_{s_id}_desc"])

        # Tłumaczenie Przycisków
        button_tags = [
            ("btn_start_home", "start"), ("btn_start_control", "start"),
            ("btn_cal_home", "cal"), ("btn_cal_control", "cal"),
            ("btn_stop_home", "stop"), ("btn_stop_control", "stop"),
            ("btn_lpm_control", "lpm"), ("btn_ppm_control", "ppm"), ("btn_test_control", "test"),
            ("btn_set0_lpm", "set0"), ("btn_set0_ppm", "set0"), ("btn_set0_test", "set0")
        ]
        for tag, dict_key in button_tags:
            if dpg.does_item_exist(tag):
                dpg.configure_item(tag, label=t[dict_key])

        # Tłumaczenie Zwykłych Tekstów
        text_tags = [
            ("txt_lang", "lang"), ("txt_res", "res"), ("txt_port", "port"),
            ("txt_target_home", "target"), ("txt_target_control", "target"),
            ("txt_logs_home", "logs"), ("txt_logs_control", "logs")
        ]
        for tag, dict_key in text_tags:
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, t[dict_key])

        # Tłumaczenie Checkboxów
        if dpg.does_item_exist("chk_debug_home"): dpg.configure_item("chk_debug_home", label=t["opencv"])
        if dpg.does_item_exist("chk_debug_control"): dpg.configure_item("chk_debug_control", label=t["opencv"])

        # Status Połączenia na Pasku
        text_val = t["status_ok"] if self.is_connected else f"{t['status_err']}{self.connection_msg}"
        if hasattr(self, "conn_text") and dpg.does_item_exist(self.conn_text):
            dpg.set_value(self.conn_text, text_val)

        if dpg.does_item_exist("plot_home_1"): dpg.configure_item("plot_home_1", label=t["plot_data"])
        if dpg.does_item_exist("plot_home_2"): dpg.configure_item("plot_home_2", label=t["plot_data"])
        if dpg.does_item_exist("plot_control"): dpg.configure_item("plot_control", label=t["plot_vision"])

        if dpg.does_item_exist("speed_text_label_control") and dpg.does_item_exist("slider_speed_control"):
            curr_speed = dpg.get_value("slider_speed_control")
            dpg.set_value("speed_text_label_control", f"{t['speed']}: {curr_speed}%")

    def update_connection_display(self):
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

        if hasattr(self, "btn_connect_icon") and dpg.does_item_exist(self.btn_connect_icon):
            dpg.configure_item(self.btn_connect_icon, texture_tag=icon_texture)
        if hasattr(self, "btn_connect_full") and dpg.does_item_exist(self.btn_connect_full):
            dpg.configure_item(self.btn_connect_full, texture_tag=full_texture)
        if hasattr(self, "conn_text") and dpg.does_item_exist(self.conn_text):
            dpg.configure_item(self.conn_text, color=text_color)
            dpg.set_value(self.conn_text, display_text)

    def build_ui(self):
        dpg.bind_theme(self.global_theme)
        with dpg.window(tag="window_root", width=self.width, height=self.height, no_title_bar=True, no_resize=True,
                        no_move=True):
            dpg.bind_item_theme("window_root", self.root_theme)

            with dpg.group(tag="page_home", show=True):
                dpg.add_spacer(height=30)
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=100)
                    with dpg.group():
                        with dpg.group(horizontal=True):
                            with dpg.child_window(width=520, height=300):
                                with dpg.plot(label="Dane", width=-1, height=-1, tag="plot_home_1"):
                                    dpg.add_plot_axis(dpg.mvXAxis, tag="home_plot1_x")
                                    dpg.add_plot_axis(dpg.mvYAxis, tag="home_plot1_y")

                                    x_data_1 = sorted([random.uniform(50000, 60000) for _ in range(8)])
                                    y_data_1 = [random.uniform(1, 7) for _ in range(8)]

                                    dpg.add_line_series(x_data_1, y_data_1, parent="home_plot1_y")
                                    dpg.add_scatter_series(x_data_1, y_data_1, parent="home_plot1_y")

                            dpg.add_spacer(width=20)

                            with dpg.child_window(width=520, height=300):
                                with dpg.plot(label="Dane", width=-1, height=-1, tag="plot_home_2"):
                                    dpg.add_plot_axis(dpg.mvXAxis, tag="home_plot2_x")
                                    dpg.add_plot_axis(dpg.mvYAxis, tag="home_plot2_y")

                                    x_data_2 = sorted([random.uniform(50000, 60000) for _ in range(8)])
                                    y_data_2 = [random.uniform(1, 7) for _ in range(8)]

                                    dpg.add_line_series(x_data_2, y_data_2, parent="home_plot2_y")
                                    dpg.add_scatter_series(x_data_2, y_data_2, parent="home_plot2_y")

                        dpg.add_spacer(height=40)

                        with dpg.group(horizontal=True):
                            with dpg.group(width=200):
                                btn_start_home = dpg.add_button(label="START", width=200, height=50,
                                                                tag="btn_start_home", callback=self.on_start)
                                dpg.add_spacer(height=10)
                                btn_calibrate_home = dpg.add_button(label="CALIBRATE", width=200, height=50,
                                                                    tag="btn_cal_home", callback=self.on_calibrate)
                                dpg.add_spacer(height=10)
                                btn_stop_home = dpg.add_button(label="FORCE STOP", width=200, height=50,
                                                               tag="btn_stop_home", callback=self.on_stop)

                                dpg.bind_item_theme(btn_start_home, self.gray_btn_theme)
                                dpg.bind_item_theme(btn_calibrate_home, self.gold_btn_theme)
                                dpg.bind_item_theme(btn_stop_home, self.red_btn_theme)

                                dpg.add_spacer(height=5)

                                txt_target = dpg.add_text("Target Prioritization:", tag="txt_target_home")
                                dpg.bind_item_theme(txt_target, self.gold_text_theme)

                                rbtn_target = dpg.add_radio_button(
                                    items=["ALL", "TT", "CT"],
                                    default_value="ALL",
                                    horizontal=True,
                                    tag="rbtn_target_home",
                                    callback=self.on_target_change
                                )
                                dpg.bind_item_theme(rbtn_target, self.violet_rbtn_theme)

                                dpg.add_spacer(height=5)
                                chk_debug = dpg.add_checkbox(
                                    label="Show OpenCV window",
                                    default_value=True,
                                    tag="chk_debug_home",
                                    callback=self.on_debug_toggle
                                )

                            dpg.add_spacer(width=60)

                            with dpg.child_window(width=470, height=220):
                                dpg.add_spacer(height=10)
                                with dpg.group(horizontal=True):
                                    dpg.add_spacer(width=10)
                                    with dpg.group():
                                        dpg.add_text("System Logs:", color=[255, 183, 0])
                                        with dpg.group(tag="logs_group_home"):
                                            dpg.add_text("<System> Robot Control Active", color=[255, 255, 255])
                                        dpg.bind_item_theme("logs_group_home", self.white_text_theme)
                                        dpg.add_spacer(height=20)
                                        dpg.add_text("Wciśnięte klawisze:", color=[255, 183, 0])
                                        dpg.add_text("[ BRAK ]", tag="current_keys_text", color=[50, 200, 50])

                            dpg.add_spacer(width=33)

                            with dpg.child_window(width=280, height=220):
                                dpg.add_spacer(height=20)
                                axes = ["X", "Y", "Z"]
                                for axis in axes:
                                    with dpg.group(horizontal=True):
                                        dpg.add_spacer(width=40)
                                        axis_label = dpg.add_text(f"{axis}: ")
                                        dpg.bind_item_theme(axis_label, self.white_text_theme)
                                        axis_value = dpg.add_text("0.00", tag=f"coord_{axis.lower()}_home")
                                        dpg.bind_item_theme(axis_value, self.white_text_theme)
                                    dpg.add_spacer(height=30)

            with dpg.group(tag="page_control", show=False):
                dpg.add_spacer(height=30)
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=100)
                    with dpg.group():
                        with dpg.group(horizontal=True):
                            with dpg.child_window(width=560, height=300):
                                with dpg.plot(label="Dane Wizyjne", width=-1, height=-1, tag="plot_control"):
                                    dpg.add_plot_axis(dpg.mvXAxis, tag="control_plot_x")
                                    dpg.add_plot_axis(dpg.mvYAxis, tag="control_plot_y")
                                    dpg.add_line_series(list(range(100)), [math.cos(x / 10) for x in range(100)],
                                                        parent="control_plot_y")
                            dpg.add_spacer(width=20)
                            with dpg.child_window(width=480, height=300):
                                dpg.add_spacer(height=10)
                                with dpg.group(horizontal=True):
                                    dpg.add_spacer(width=10)
                                    with dpg.group():
                                        dpg.add_text("System Logs:", color=[255, 183, 0])
                                        with dpg.group(tag="logs_group_control"):
                                            self.add_log("<System> Robot Control Active", parent="logs_group_control")
                                        dpg.bind_item_theme("logs_group_control", self.white_text_theme)

                        dpg.add_spacer(height=40)

                        with dpg.group(horizontal=True):
                            with dpg.group():
                                btn_start = dpg.add_button(label="START", width=200, height=50, tag="btn_start_control",
                                                           callback=self.on_start)
                                dpg.add_spacer(height=10)
                                btn_calibrate = dpg.add_button(label="CALIBRATE", width=200, height=50,
                                                               tag="btn_cal_control", callback=self.on_calibrate)
                                dpg.add_spacer(height=10)
                                btn_stop = dpg.add_button(label="FORCE STOP", width=200, height=50,
                                                          tag="btn_stop_control", callback=self.on_stop)

                                dpg.bind_item_theme(btn_start, self.gray_btn_theme)
                                dpg.bind_item_theme(btn_calibrate, self.gold_btn_theme)
                                dpg.bind_item_theme(btn_stop, self.red_btn_theme)

                                dpg.add_spacer(height=5)

                                txt_target = dpg.add_text("Target Prioritization:")
                                dpg.bind_item_theme(txt_target, self.gold_text_theme)

                                self.rbtn_target = dpg.add_radio_button(
                                    items=["ALL", "TT", "CT"],
                                    default_value="ALL",
                                    horizontal=True,
                                    callback=self.on_target_change
                                )
                                dpg.bind_item_theme(self.rbtn_target, self.violet_rbtn_theme)

                                dpg.add_spacer(height=5)
                                self.chk_debug = dpg.add_checkbox(
                                    label="Show OpenCV window",
                                    default_value=True,
                                    callback=self.on_debug_toggle
                                )

                            dpg.add_spacer(width=40)

                            with dpg.group():
                                actions = [("Wciśnij LPM", "lpm"), ("Wciśnij PPM", "ppm"), ("Test Chwytaka", "test")]
                                for action_label, action_key in actions:
                                    with dpg.group(horizontal=True):
                                        btn_action = dpg.add_button(label=action_label, width=200, height=45, tag=f"btn_{action_key}_control")
                                        dpg.bind_item_theme(btn_action, self.gold_btn_theme)

                                        dpg.add_spacer(width=5)
                                        btn_left = dpg.add_button(label="<", width=70, height=45)
                                        dpg.bind_item_theme(btn_left, self.gold_btn_theme)

                                        dpg.add_spacer(width=5)
                                        btn_right = dpg.add_button(label=">", width=70, height=45)
                                        dpg.bind_item_theme(btn_right, self.gold_btn_theme)

                                        dpg.add_spacer(width=5)
                                        btn_set_zero = dpg.add_button(label="Set 0", width=80, height=45, tag=f"btn_set0_{action_key}")
                                        dpg.bind_item_theme(btn_set_zero, self.gray_btn_theme)

                                    dpg.add_spacer(height=10)

                                dpg.add_spacer(height=10)

                                with dpg.table(header_row=False, width=470, borders_innerH=False, borders_outerH=False,
                                               borders_innerV=False, borders_outerV=False):
                                    dpg.add_table_column(width_fixed=True, init_width_or_weight=90)
                                    dpg.add_table_column()
                                    with dpg.table_row():
                                        txt_speed = dpg.add_text("Speed: 75%", tag="speed_text_label_control")
                                        dpg.bind_item_theme(txt_speed, self.white_text_theme)

                                        slider_speed = dpg.add_slider_int(width=370, default_value=75, format="", tag="slider_speed_control", callback=self.on_speed_change_control)
                                        dpg.bind_item_theme(slider_speed, self.slider_theme)

                            dpg.add_spacer(width=40)

                            with dpg.child_window(width=280, height=220):
                                dpg.add_spacer(height=20)
                                axes    = ["X", "Y", "Z"]
                                for axis in axes:
                                    with dpg.group(horizontal=True):
                                        dpg.add_spacer(width=40)
                                        axis_label = dpg.add_text(f"{axis}: ")
                                        dpg.bind_item_theme(axis_label, self.white_text_theme)
                                        axis_value = dpg.add_text("0.00", tag=f"coord_{axis.lower()}_control")
                                        dpg.bind_item_theme(axis_value, self.white_text_theme)
                                    dpg.add_spacer(height=30)

            with dpg.group(tag="page_settings", show=False):
                dpg.add_spacer(height=60)
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=310)

                    with dpg.group():
                        with dpg.child_window(width=600, height=50, no_scrollbar=True) as row_lang:
                            txt_lang = dpg.add_text("Language", tag="txt_lang", pos=[20, 13])
                            dpg.bind_item_theme(txt_lang, self.white_text_theme)
                            # combo box sztywno przypięty na osi X (400px), niezależnie od tekstu!
                            combo_lang = dpg.add_combo(items=["English", "Polski"], default_value="English", width=180, pos=[400, 13], callback=self.on_language_change)
                            dpg.bind_item_theme(combo_lang, self.gold_combo_theme)
                        dpg.bind_item_theme(row_lang, self.settings_row_theme)
                        dpg.add_spacer(height=10)

                        with dpg.child_window(width=600, height=50, no_scrollbar=True) as row_res:
                            txt_res = dpg.add_text("Resolution", tag="txt_res", pos=[20, 13])
                            dpg.bind_item_theme(txt_res, self.white_text_theme)
                            combo_res = dpg.add_combo(items=["1280x720", "1920x1080"], default_value="1280x720", width=180, pos=[400, 13])
                            dpg.bind_item_theme(combo_res, self.gold_combo_theme)
                        dpg.bind_item_theme(row_res, self.settings_row_theme)
                        dpg.add_spacer(height=10)

                        with dpg.child_window(width=600, height=50, no_scrollbar=True) as row_port:
                            txt_port = dpg.add_text("COM Port", tag="txt_port", pos=[20, 13])
                            dpg.bind_item_theme(txt_port, self.white_text_theme)

                            # Pobranie dostępnych portów COM w systemie
                            available_ports = [port.device for port in serial.tools.list_ports.comports()]
                            if not available_ports:
                                available_ports = ["COM3"]  # Fallback

                            combo_port = dpg.add_combo(items=available_ports, default_value=available_ports[0],
                                                       width=180, pos=[400, 13], callback=self.on_port_change)
                            dpg.bind_item_theme(combo_port, self.gold_combo_theme)
                        dpg.bind_item_theme(row_port, self.settings_row_theme)
                        dpg.add_spacer(height=10)

                        for _ in range(5):
                            with dpg.child_window(width=600, height=50, no_scrollbar=True) as row_empty:
                                pass
                            dpg.bind_item_theme(row_empty, self.settings_row_theme)
                            dpg.add_spacer(height=10)

            with dpg.group(tag="page_stat", show=False):
                dpg.add_spacer(height=35)

                card_data = [
                    ("lmb", "tex_stat_lmb"), ("rmb", "tex_stat_rmb"),
                    ("time", "tex_stat_time"), ("mouse", "tex_stat_mouse"),
                    ("dist", "tex_stat_dist"), ("energy", "tex_stat_energy"),
                    ("unknown", ""), ("keys", "tex_stat_keys")
                ]

                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=90)
                    with dpg.group():
                        for row in range(2):
                            with dpg.group(horizontal=True):
                                for col in range(4):
                                    idx = row * 4 + col
                                    c_id, c_tex = card_data[idx]
                                    with dpg.child_window(width=255, height=295) as card_win:
                                        dpg.add_spacer(height=5)
                                        if c_tex:
                                            with dpg.group(horizontal=True):
                                                dpg.add_spacer(width=72)
                                                dpg.add_image(c_tex, width=80, height=80)
                                        else:
                                            dpg.add_spacer(height=80)

                                        dpg.add_spacer(height=15)

                                        title_txt = dpg.add_text("", tag=f"stat_title_{c_id}")
                                        dpg.bind_item_theme(title_txt, self.white_text_theme)

                                        dpg.add_spacer(height=2)
                                        desc_txt = dpg.add_text("", tag=f"stat_desc_{c_id}", wrap=225)
                                        dpg.bind_item_theme(desc_txt, self.gold_text_theme)

                                        dpg.add_spacer(height=20)

                                        val = random.randint(1000, 999999)
                                        val_btn = dpg.add_button(label=str(val), width=225, height=45,
                                                                 tag=f"stat_val_{c_id}")
                                        dpg.bind_item_theme(val_btn, self.stat_value_theme)

                                    dpg.bind_item_theme(card_win, self.stat_card_theme)
                                    if col < 3:
                                        dpg.add_spacer(width=20)
                            if row == 0:
                                dpg.add_spacer(height=20)
        with dpg.window(tag="window_dim", width=self.width, height=self.height, pos=(0, 0), no_title_bar=True,
                        no_resize=True, no_move=True, show=False):
            dpg.bind_item_theme("window_dim", self.dim_theme)
            dpg.add_button(width=self.width, height=self.height, callback=self.toggle_sidebar)
            dpg.bind_item_theme(dpg.last_item(), self.invisible_btn_theme)

        with dpg.window(tag="window_sidebar", width=60, height=self.height, pos=(0, 0), no_title_bar=True,
                        no_resize=True, no_move=True):
            dpg.bind_item_theme("window_sidebar", self.sidebar_theme)
            with dpg.child_window(tag="sidebar_child", width=60, height=self.height, border=False, no_scrollbar=True):
                self.nav_texts = []
                with dpg.group(horizontal=True):
                    self.btn_toggle = dpg.add_image_button(texture_tag="tex_menu", width=50, height=50,
                                                           callback=self.toggle_sidebar)
                    dpg.bind_item_theme(self.btn_toggle, self.transparent_btn_theme)
                    with dpg.group():
                        dpg.add_spacer(height=15)
                        self.title_text = dpg.add_text("CSAimBot 1.0", show=False)
                        dpg.bind_item_theme(self.title_text, self.white_text_theme)

                dpg.add_spacer(height=20)
                self.nav_texts = []
                for page_tag, item_config in self.nav_config.items():
                    btn_tag = f"nav_btn_{page_tag}"
                    text_tag = f"nav_text_{page_tag}"
                    self.nav_elements[page_tag] = {"btn": btn_tag, "text": text_tag}

                    with dpg.group(horizontal=True):
                        btn = dpg.add_image_button(texture_tag=item_config["inactive_tex"], width=50, height=50,
                                                   callback=self.switch_page, user_data=page_tag, tag=btn_tag)
                        dpg.bind_item_theme(btn, self.transparent_btn_theme)

                        with dpg.group():
                            dpg.add_spacer(height=15)
                            txt = dpg.add_text(item_config["label"], show=False, tag=text_tag)
                            dpg.bind_item_theme(txt, self.gray_text_theme)

                            # Rejestrujemy kliknięcie lewym przyciskiem myszy na samym tekście
                            with dpg.item_handler_registry() as text_click_handler:
                                dpg.add_item_clicked_handler(button=0, callback=self.switch_page, user_data=page_tag)
                            dpg.bind_item_handler_registry(txt, text_click_handler)

                        self.nav_texts.append(txt)
                    dpg.add_spacer(height=5)

                dpg.add_spacer(height=210)

                with dpg.group(tag="group_conn_text_placeholder", show=True):
                    dpg.add_spacer(height=32)

                with dpg.group(tag="group_conn_text", show=False):
                    with dpg.group(horizontal=True):
                        dpg.add_spacer(width=10)
                        color = [80, 255, 80] if self.is_connected else [255, 80, 80]
                        text_val = "Status: OK" if self.is_connected else f"Error: {self.connection_msg}"
                        self.conn_text = dpg.add_text(text_val, color=color)
                    dpg.add_spacer(height=5)

                tex_icon = "tex_conn_green" if self.is_connected else "tex_conn_red"
                tex_full = "tex_conn_green_full" if self.is_connected else "tex_conn_red_full"

                with dpg.group(horizontal=True, tag="group_conn_icon", show=True):
                    self.btn_connect_icon = dpg.add_image_button(texture_tag=tex_icon, width=50, height=50, indent=2,
                                                           callback=self.on_connect_click) # Dodaj to
                    dpg.bind_item_theme(self.btn_connect_icon, self.transparent_btn_theme)

                with dpg.group(horizontal=True, tag="group_conn_full", show=False):
                    self.btn_connect_full = dpg.add_image_button(texture_tag=tex_full, width=220, height=50, indent=2,
                                                           callback=self.on_connect_click) # Dodaj to
                    dpg.bind_item_theme(self.btn_connect_full, self.transparent_btn_theme)

    def on_speed_change_control(self, sender, app_data):
        t = self.lang_dict[self.current_lang]
        dpg.set_value("speed_text_label_control", f"{t['speed']}: {app_data}%")

    def on_target_change(self, sender, app_data):
        # Synchronizacja elementu na obu podstronach (Home i Control)
        for tag in ["rbtn_target_home", "rbtn_target_control"]:
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, app_data)

                # Nałożenie odpowiedniego koloru na obu stronach
                if app_data == "TT":
                    dpg.bind_item_theme(tag, self.yellow_rbtn_theme)
                elif app_data == "CT":
                    dpg.bind_item_theme(tag, self.blue_rbtn_theme)
                else:
                    dpg.bind_item_theme(tag, self.violet_rbtn_theme)

        # Wysłanie komendy
        self.pipe.send({"cmd": "SET_TARGET", "value": app_data})

    def on_debug_toggle(self, sender, app_data):
        # Synchronizacja checkboxa na obu podstronach
        for tag in ["chk_debug_home", "chk_debug_control"]:
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, app_data)

        self.pipe.send({"cmd": "DEBUG", "value": app_data})

    def add_log(self, text, color=[255, 255, 255], parent=None):
        if parent:
            if dpg.does_item_exist(parent):
                dpg.add_text(text, parent=parent, color=color)
        else:
            for group in ["logs_group_control", "logs_group_home"]:
                if dpg.does_item_exist(group):
                    dpg.add_text(text, parent=group, color=color)

    def on_port_change(self, sender, app_data):
        self.connection_state = "connecting"
        self.update_connection_display()
        self.comms_pipe.send({"cmd": "CHANGE_PORT", "value": app_data})

    def on_connect_click(self, sender, app_data):
        # Łączymy się tylko, jeśli aktualnie nie jesteśmy połączeni
        if not self.is_connected:
            self.connection_state = "connecting"
            self.update_connection_display()
            self.comms_pipe.send({"cmd": "CONNECT"})
        else:
            self.connection_state = "disconnecting"
            self.update_connection_display()
            self.comms_pipe.send({"cmd": "DISCONNECT"})
    def on_start(self, s, a):
        self.pipe.send({"cmd": "START"})

    def on_stop(self, s, a):
        self.pipe.send({"cmd": "STOP"})

    def on_calibrate(self, s, a):
        self.pipe.send({"cmd": "CALIBRATE"})

    def poll_pipe(self):
        while self.running:
            while self.pipe.poll():
                msg = self.pipe.recv()
                if msg.get("type") == "coords":
                    for axis in ["x", "y", "z"]:
                        val = str(msg.get(axis))
                        tag_control = f"coord_{axis}_control"
                        tag_home = f"coord_{axis}_home"

                        if dpg.does_item_exist(tag_control):
                            dpg.set_value(tag_control, val)
                        if dpg.does_item_exist(tag_home):
                            dpg.set_value(tag_home, val)
            while self.comms_pipe.poll():
                msg = self.comms_pipe.recv()
                if msg.get("type") == "connection_status":
                    self.connection_state = msg.get("status")
                    self.is_connected = (self.connection_state == "connected")
                    self.update_connection_display()
                elif msg.get("type") == "keyboard":
                    keys = msg.get("keys")
                    if keys:
                        self.comms_pipe.send({"cmd": "SEND", "value": f"0,0,{keys}"})
                    display_text = f"[ {keys.upper()} ]" if keys else "[ BRAK ]"
                    if dpg.does_item_exist("current_keys_text"):
                        dpg.set_value("current_keys_text", display_text)
                elif msg.get("type") == "esp_msg":
                    esp_text = msg.get("value")
                    print(f"<ESP32> {esp_text}")
                time.sleep(0.01)

    def run(self):
        dpg.set_primary_window("window_root", True)
        dpg.show_viewport()

        while dpg.is_dearpygui_running():
            for page_tag, elements in self.nav_elements.items():
                config = self.nav_config.get(page_tag)
                if dpg.does_item_exist(elements["btn"]) and dpg.does_item_exist(elements["text"]):
                    if page_tag == self.active_page_tag:
                        dpg.configure_item(elements["btn"], texture_tag=config["active_tex"])
                        dpg.bind_item_theme(elements["text"], self.gold_text_theme)
                    else:
                        dpg.configure_item(elements["btn"], texture_tag=config["inactive_tex"])
                        dpg.bind_item_theme(elements["text"], self.white_text_theme)


            dpg.render_dearpygui_frame()

        self.running = False
        self.pipe.send({"cmd": "QUIT"})
        self.comms_pipe.send({"cmd": "QUIT"})
        dpg.destroy_context()


if __name__ == "__main__":
    import multiprocessing

    parent_pipe, child_pipe = multiprocessing.Pipe()
    app_instance = GUI(child_pipe)
    app_instance.run()