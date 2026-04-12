import dearpygui.dearpygui as dpg

class GUI:
    def __init__(self, pipe_conn):
        self.pipe = pipe_conn
        
        dpg.create_context()
        dpg.create_viewport(title='CSAimBot Control Panel', width=450, height=320, resizable=True)
        dpg.setup_dearpygui()

        with dpg.window(label="Main Window", width=450, height=320, no_collapse=True, no_close=True, no_move=True, no_title_bar=True):
            dpg.add_text("CSAimBot", color=[100, 200, 255])
            dpg.add_separator()
            dpg.add_spacer(height=10)

            dpg.add_text("Detection Control")
            with dpg.group(horizontal=True):
                self.btn_start = dpg.add_button(label="START", width=200, height=40, callback=self.on_start)
                self.btn_stop = dpg.add_button(label="STOP", width=200, height=40, callback=self.on_stop)

            dpg.add_spacer(height=15)
            dpg.add_text("Target Prioritization")
            self.rbtn_target = dpg.add_radio_button(
                items=["ALL", "TT", "CT"],
                default_value="ALL",
                horizontal=True,
                callback=self.on_target_change
            )

            dpg.add_spacer(height=15)
            dpg.add_text("Debugging")
            self.chk_debug = dpg.add_checkbox(label="Show OpenCV window", default_value=True, callback=self.on_debug_toggle)

            self.setup_themes()

    def create_btn_theme(self, color, hover_color, active_color):
        with dpg.theme() as theme_id:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, color)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, hover_color)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, active_color)
                dpg.add_theme_color(dpg.mvThemeCol_Text, [255, 255, 255])
        return theme_id
    
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
        self.gray_btn_theme = self.create_btn_theme([50, 50, 50], [70, 70, 70], [30, 30, 30])
        self.green_btn_theme = self.create_btn_theme([50, 200, 50], [70, 255, 70], [30, 150, 30])
        self.red_btn_theme = self.create_btn_theme([200, 50, 50], [255, 70, 70], [150, 30, 30])
        dpg.bind_item_theme(self.btn_start, self.gray_btn_theme)
        dpg.bind_item_theme(self.btn_stop, self.red_btn_theme)

        self.yellow_rbtn_theme = self.create_rbtn_theme([50, 50, 0], [70, 70, 0], [255, 255, 0], [255, 255, 255])
        self.blue_rbtn_theme = self.create_rbtn_theme([0, 0, 50], [0, 0, 70], [0, 255, 255], [255, 255, 255])
        self.violet_rbtn_theme = self.create_rbtn_theme([50, 0, 50], [70, 0, 70], [255, 0, 255], [255, 255, 255])
        dpg.bind_item_theme(self.rbtn_target, self.violet_rbtn_theme)

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

    def on_start(self, sender, app_data):
        self.pipe.send({"cmd": "START"})
        dpg.bind_item_theme(self.btn_start, self.green_btn_theme)
        dpg.bind_item_theme(self.btn_stop, self.gray_btn_theme)

    def on_stop(self, sender, app_data):
        self.pipe.send({"cmd": "STOP"})
        dpg.bind_item_theme(self.btn_start, self.gray_btn_theme)
        dpg.bind_item_theme(self.btn_stop, self.red_btn_theme)

    def on_debug_toggle(self, sender, app_data):
        self.pipe.send({"cmd": "DEBUG", "value": app_data})

    def run(self):
        dpg.show_viewport()
        dpg.start_dearpygui()
        
        self.pipe.send({"cmd": "QUIT"})
        dpg.destroy_context()