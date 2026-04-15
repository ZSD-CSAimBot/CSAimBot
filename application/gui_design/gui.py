import math
import threading

import dearpygui.dearpygui as dpg


class GUI:
    def __init__(self, pipe_conn):
        self.pipe = pipe_conn
        self.running = True
        self.sidebar_expanded = False

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

    # --- Logika Nawigacji ---
    def switch_page(self, sender, app_data, user_data):
        # user_data to tag strony, którą chcemy pokazać
        pages = ["page_home", "page_control"]
        for page in pages:
            if dpg.does_item_exist(page):
                dpg.configure_item(page, show=(page == user_data))

        # Zaktualizuj globalny stan, pętla renderująca zajmie się resztą
        self.active_page_tag = user_data

        # Jeśli menu jest rozwinięte, zamknij je po wyborze strony (opcjonalnie)
        if self.sidebar_expanded:
            self.toggle_sidebar(None, None)

    def setup_fonts(self):
        with dpg.font_registry():
            # Upewnij się, że ścieżka do pliku jest poprawna
            try:
                with dpg.font("application/gui_design/fonts/Inter.ttf", 16) as self.default_font:
                    dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                    dpg.add_font_range(0x0100, 0x017F)  # Polskie znaki
                dpg.bind_font(self.default_font)
            except:
                print("Nie znaleziono czcionki, używam domyślnej.")

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
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, [47, 49, 54, 255])
                dpg.add_theme_color(dpg.mvThemeCol_Text, [255, 215, 0, 255])
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 10, 10)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)

            with dpg.theme_component(dpg.mvPlot):
                dpg.add_theme_color(dpg.mvPlotCol_PlotBg, [25, 25, 30, 255])
                dpg.add_theme_color(dpg.mvPlotCol_PlotBorder, [47, 49, 54, 255])

        self.gray_btn_theme = self.create_btn_theme([50, 50, 50], [70, 70, 70], [30, 30, 30])
        self.green_btn_theme = self.create_btn_theme([50, 200, 50], [70, 255, 70], [30, 150, 30])
        self.red_btn_theme = self.create_btn_theme([200, 0, 0], [220, 0, 0], [180, 0, 0])
        self.gold_btn_theme = self.create_btn_theme([255, 195, 10], [255, 200, 0], [255, 160, 0], [40, 40, 60])
        self.transparent_btn_theme = self.create_btn_theme([0, 0, 0, 0], [255, 255, 255, 20], [255, 255, 255, 40])

        # --- PRZYWRÓCONE MOTYWY DLA RADIO BUTTONÓW ---
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
                dpg.add_theme_color(dpg.mvThemeCol_Text, [255, 195, 10, 255])

        with dpg.theme() as self.dim_theme:
            with dpg.theme_component(dpg.mvWindowAppItem):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, [0, 0, 0, 180])
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)

        with dpg.theme() as self.slider_theme:
            with dpg.theme_component(dpg.mvSliderInt):
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, [70, 70, 70, 255])
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, [255, 183, 0, 255])
                dpg.add_theme_style(dpg.mvStyleVar_GrabRounding, 12)

        # Motyw dla głównego tła aplikacji
        with dpg.theme() as self.root_theme:
            with dpg.theme_component(dpg.mvWindowAppItem):
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)
                # >>> TUTAJ ZMIENIASZ GŁÓWNY KOLOR TŁA (np. [30, 30, 30, 255]) <<<
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, [30, 30, 35, 255])

                # Motyw dla okna bocznego (Sidebar)
        with dpg.theme() as self.sidebar_theme:
            with dpg.theme_component(dpg.mvWindowAppItem):
                # >>> TUTAJ ZMIENIASZ KOLOR MENU BOCZNEGO <<<
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, [30, 30, 35, 255])
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)

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
        with dpg.texture_registry(show=False):
            def load_and_add(path, tag):
                try:
                    img = dpg.load_image(path)
                    if img:
                        dpg.add_static_texture(width=img[0], height=img[1], default_value=img[3], tag=tag)
                    else:
                        # Zapasowa przezroczysta tekstura (1x1 piksel), zapobiega crashom!
                        dpg.add_static_texture(width=1, height=1, default_value=[0.0, 0.0, 0.0, 0.0], tag=tag)
                        print(f"UWAGA: Brak pliku graficznego -> {path}")
                except Exception as e:
                    dpg.add_static_texture(width=1, height=1, default_value=[0.0, 0.0, 0.0, 0.0], tag=tag)
                    print(f"UWAGA: Błąd wczytywania -> {path}")

            # Menu and X
            load_and_add("application/gui_design/icons/ikona_hamburger.png", "tex_menu")
            load_and_add("application/gui_design/icons/ikona_X.png", "tex_x")

            # Connect
            load_and_add("application/gui_design/icons/ikona_connect_red.png", "tex_connect_red")
            load_and_add("application/gui_design/icons/ikona_connect_yellow.png", "tex_connect_yellow")
            load_and_add("application/gui_design/icons/ikona_connect_green.png", "tex_connect_green")

            # Active
            load_and_add("application/gui_design/icons/ikona_home.png", "tex_home")
            load_and_add("application/gui_design/icons/ikona_control.png", "tex_control")
            load_and_add("application/gui_design/icons/ikona_stat.png", "tex_stat")
            load_and_add("application/gui_design/icons/ikona_settings.png", "tex_settings")

            # Inactive
            load_and_add("application/gui_design/icons/ikona_home_inactive.png", "tex_home_inactive")
            load_and_add("application/gui_design/icons/ikona_control_inactive.png", "tex_control_inactive")
            load_and_add("application/gui_design/icons/ikona_stat_inactive.png", "tex_stat_inactive")
            load_and_add("application/gui_design/icons/ikona_settings_inactive.png", "tex_settings_inactive")

    def toggle_sidebar(self, sender, app_data):
        self.sidebar_expanded = not self.sidebar_expanded
        new_width = 240 if self.sidebar_expanded else 60
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

    def build_ui(self):
        dpg.bind_theme(self.global_theme)
        # --- WARSTWA 0: SPÓD (GŁÓWNA TREŚĆ) ---
        with dpg.window(tag="window_root", width=self.width, height=self.height, no_title_bar=True, no_resize=True,
                        no_move=True):
            dpg.bind_item_theme("window_root", self.root_theme)

            # ---------------------------------------------------------------------------------
            # PAGE: HOME (Dwa wykresy obok siebie)
            # ---------------------------------------------------------------------------------
            with dpg.group(tag="page_home", show=True):
                dpg.add_spacer(height=100)
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=160)
                    with dpg.group():
                        with dpg.group(horizontal=True):
                            sdata = [math.sin(i / 10) * 4 + 4 for i in range(500, 601, 1)]
                            xdata = list(range(500, 601, 1))

                            with dpg.child_window(width=440, height=260):
                                with dpg.plot(label="Wykres 1", width=-1, height=-1):
                                    dpg.add_plot_axis(dpg.mvXAxis, tag="home_plot1_x")
                                    # Dodajemy TAG "home_plot1_y"
                                    dpg.add_plot_axis(dpg.mvYAxis, tag="home_plot1_y")
                                    # Przypisujemy linię do osi Y uzywając parent=
                                    dpg.add_line_series(xdata, sdata, parent="home_plot1_y")

                            dpg.add_spacer(width=20)

                            with dpg.child_window(width=440, height=260):
                                with dpg.plot(label="Wykres 2", width=-1, height=-1):
                                    dpg.add_plot_axis(dpg.mvXAxis, tag="home_plot2_x")
                                    # Dodajemy TAG "home_plot2_y"
                                    dpg.add_plot_axis(dpg.mvYAxis, tag="home_plot2_y")
                                    # Przypisujemy linię do osi Y uzywając parent=
                                    dpg.add_line_series(xdata, sdata, parent="home_plot2_y")

            # ---------------------------------------------------------------------------------
            # PAGE: CONTROL PANEL (Zgodnie z Twoim nowym projektem)
            # ---------------------------------------------------------------------------------
            with dpg.group(tag="page_control", show=False):
                dpg.add_spacer(height=30)
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=100)
                    with dpg.group():
                        # Góra: Wykres + Logi
                        with dpg.group(horizontal=True):
                            with dpg.child_window(width=560, height=300):
                                with dpg.plot(label="Dane Wizyjne", width=-1, height=-1):
                                    dpg.add_plot_axis(dpg.mvXAxis, tag="control_plot_x")
                                    # Dodajemy TAG "control_plot_y"
                                    dpg.add_plot_axis(dpg.mvYAxis, tag="control_plot_y")
                                    # Przypisujemy linię do osi Y
                                    dpg.add_line_series(list(range(100)), [math.cos(x / 10) for x in range(100)],
                                                        parent="control_plot_y")
                            dpg.add_spacer(width=20)
                            with dpg.child_window(width=400, height=300):
                                dpg.add_text("System Logs:", color=[255, 183, 0])
                                with dpg.group(tag="logs_group_control"):
                                    self.add_log("<System> Robot Control Active", parent="logs_group_control")
                                dpg.bind_item_theme("logs_group_control", self.white_text_theme)

                        dpg.add_spacer(height=40)

                        # Dół: Sterowanie
                        with dpg.group(horizontal=True):
                            # Przyciski główne
                            # Kolumna 1: Przyciski główne i opcje
                            with dpg.group(width=200):
                                b1 = dpg.add_button(label="START", width=200, height=50, callback=self.on_start)
                                dpg.add_spacer(height=10)
                                b2 = dpg.add_button(label="CALIBRATE", width=200, height=50, callback=self.on_calibrate)
                                dpg.add_spacer(height=10)
                                b3 = dpg.add_button(label="FORCE STOP", width=200, height=50, callback=self.on_stop)

                                dpg.bind_item_theme(b1, self.gray_btn_theme)
                                dpg.bind_item_theme(b2, self.gold_btn_theme)
                                dpg.bind_item_theme(b3, self.red_btn_theme)

                                # --- Przywrócone opcje celowania i okna ---
                                dpg.add_spacer(height=5)

                                txt_target = dpg.add_text("Target Prioritization:")
                                dpg.bind_item_theme(txt_target, self.gold_text_theme)  # Złoty akcent dla czytelności

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

                            # Zmniejszamy też pustą przestrzeń między kolumnami!
                            dpg.add_spacer(width=30)

                            # Było 50

                            # Kolumna 2: Macierz osi i suwak na dole
                            with dpg.group():  # Usunięto sztywne width! Elementy same nadadzą szerokość

                                # 1. Macierz przycisków (wiersze)
                                for label in ["Wciśnij LPM", "Wciśnij PPM", "Test Chwytaka"]:
                                    with dpg.group(horizontal=True):
                                        ba = dpg.add_button(label=label, width=200, height=45)
                                        dpg.bind_item_theme(ba, self.gold_btn_theme)

                                        # Dodałem małe spacery (width=5) między guzikami, żeby się nie zlewały
                                        dpg.add_spacer(width=5)
                                        bl = dpg.add_button(label="<", width=70, height=45)
                                        dpg.bind_item_theme(bl, self.gold_btn_theme)

                                        dpg.add_spacer(width=5)
                                        br = dpg.add_button(label=">", width=70, height=45)
                                        dpg.bind_item_theme(br, self.gold_btn_theme)

                                        dpg.add_spacer(width=5)
                                        bs = dpg.add_button(label="Set 0", width=80, height=45)
                                        dpg.bind_item_theme(bs, self.gray_btn_theme)

                                    dpg.add_spacer(height=10)

                                dpg.add_spacer(height=10)

                                # 2. Suwak prędkości (wyląduje idealnie pod przyciskami)
                                with dpg.group(horizontal=True):
                                    st = dpg.add_text("Speed: 75%", tag="speed_text_label_control")
                                    dpg.bind_item_theme(st, self.white_text_theme)

                                    dpg.add_spacer(width=10)

                                    # Suwak na 260px - ładnie dopasuje się do szerokości przycisków wyżej
                                    sl = dpg.add_slider_int(width=380, default_value=75, format="",
                                                            callback=self.on_speed_change_control)
                                    dpg.bind_item_theme(sl, self.slider_theme)

                            # Zmniejszamy odstęp przed koordynatami
                            dpg.add_spacer(width=10)

                            # Koordynaty
                            with dpg.child_window(width=240, height=220):
                                dpg.add_spacer(height=20)
                                for axis in ["X", "Y", "Z"]:
                                    with dpg.group(horizontal=True):
                                        dpg.add_spacer(width=30)
                                        al = dpg.add_text(f"{axis}: ");
                                        dpg.bind_item_theme(al, self.white_text_theme)
                                        av = dpg.add_text("0.00", tag=f"coord_{axis.lower()}_control");
                                        dpg.bind_item_theme(av, self.white_text_theme)
                                    dpg.add_spacer(height=30)

        # --- WARSTWA 1: PRZYCIEMNIENIE ---
        with dpg.window(tag="window_dim", width=self.width, height=self.height, pos=(0, 0), no_title_bar=True,
                        no_resize=True, no_move=True, show=False):
            dpg.bind_item_theme("window_dim", self.dim_theme)
            dpg.add_button(width=self.width, height=self.height, callback=self.toggle_sidebar)
            dpg.bind_item_theme(dpg.last_item(), self.invisible_btn_theme)

        # --- WARSTWA 2: SIDEBAR ---
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
                        self.title_text = dpg.add_text("CSAimBot 1.0", show=False);
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
                        self.nav_texts.append(txt)
                    dpg.add_spacer(height=5)

                dpg.add_text(" \n" * 16)
                with dpg.group(horizontal=True):

                    btn_connect = dpg.add_image_button(texture_tag="tex_connect_red", width=50, height=50)
                    dpg.bind_item_theme(btn_connect, self.transparent_btn_theme)

    def on_speed_change_control(self, sender, app_data):
        dpg.set_value("speed_text_label_control", f"Speed: {app_data}%")

    def on_target_change(self, sender, app_data):
        if app_data == "TT":
            self.pipe.send({"cmd": "SET_TARGET", "value": "TT"})
            dpg.bind_item_theme(self.rbtn_target, self.yellow_rbtn_theme)
        elif app_data == "CT":
            self.pipe.send({"cmd": "SET_TARGET", "value": "CT"})
            dpg.bind_item_theme(self.rbtn_target, self.blue_rbtn_theme)
        else:
            self.pipe.send({"cmd": "SET_TARGET", "value": "ALL"})
            dpg.bind_item_theme(self.rbtn_target, self.violet_rbtn_theme)

    def on_debug_toggle(self, sender, app_data):
        self.pipe.send({"cmd": "DEBUG", "value": app_data})

    def add_log(self, text, color=[255, 255, 255], parent="logs_group"):
        if dpg.does_item_exist(parent):
            dpg.add_text(text, parent=parent, color=color)

    # ... Callbacks (on_start, poll_pipe itp.) zostają bez zmian ...
    def on_start(self, s, a):
        self.pipe.send({"cmd": "START"})

    def on_stop(self, s, a):
        self.pipe.send({"cmd": "STOP"})

    def on_calibrate(self, s, a):
        self.pipe.send({"cmd": "CALIBRATE"})

    def poll_pipe(self):
        while self.running:
            if self.pipe.poll(0.05):
                msg = self.pipe.recv()
                # Logika aktualizacji koordynatów dla obu stron
                if msg.get("type") == "coords":
                    for axis in ["x", "y", "z"]:
                        tag = f"coord_{axis}_control"
                        if dpg.does_item_exist(tag):
                            dpg.set_value(tag, str(msg.get(axis)))

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
                        dpg.bind_item_theme(elements["text"], self.gold_text_theme)

            dpg.render_dearpygui_frame()

        self.running = False
        self.pipe.send({"cmd": "QUIT"})
        dpg.destroy_context()
