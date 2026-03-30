import dearpygui.dearpygui as dpg

class GUI:
    def __init__(self, pipe_conn):
        self.pipe = pipe_conn
        
        dpg.create_context()
        dpg.create_viewport(title='CSAimBot Control Panel', width=450, height=250, resizable=False)
        dpg.setup_dearpygui()

        with dpg.window(label="Main Window", width=450, height=250, no_collapse=True, no_close=True, no_move=True, no_title_bar=True):
            dpg.add_text("CSAimBot", color=[100, 200, 255])
            dpg.add_separator()
            dpg.add_spacer(height=10)

            dpg.add_text("Detection Control")
            with dpg.group(horizontal=True):
                self.btn_start = dpg.add_button(label="START", width=200, height=40, callback=self.on_start)
                self.btn_stop = dpg.add_button(label="STOP", width=200, height=40, callback=self.on_stop)

            dpg.add_spacer(height=15)

            dpg.add_text("Debugging")
            self.chk_debug = dpg.add_checkbox(label="Show OpenCV window", default_value=True, callback=self.on_debug_toggle)

    def on_start(self, sender, app_data):
        self.pipe.send({"cmd": "START"})

    def on_stop(self, sender, app_data):
        self.pipe.send({"cmd": "STOP"})

    def on_debug_toggle(self, sender, app_data):
        self.pipe.send({"cmd": "DEBUG", "value": app_data})

    def run(self):
        dpg.show_viewport()
        dpg.start_dearpygui()
        
        self.pipe.send({"cmd": "QUIT"})
        dpg.destroy_context()