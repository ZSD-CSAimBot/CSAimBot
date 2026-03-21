int pos_X = 0;
int pos_Y = 0;
String pressed_keys = "";

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(30);
}

void loop() {
  if (Serial.available() > 0) {

    String data = Serial.readStringUntil('\r');
    data.trim();

    if (data.length() == 0) {
      return;
    }

    // Find positions of commas
    int comma_idx_1 = data.indexOf(',');
    int comma_idx_2 = data.indexOf(',', comma_idx_1 + 1);

    if (comma_idx_1 > 0) {
      // Parse X
      String text_x = data.substring(0, comma_idx_1);
      pos_X = text_x.toInt();

      // Parse Y
      String text_y;
      if (comma_idx_2 > 0) {
        text_y = data.substring(comma_idx_1 + 1, comma_idx_2);
        // Parse pressed keys
        pressed_keys = data.substring(comma_idx_2 + 1);
      } else {
        text_y = data.substring(comma_idx_1 + 1);
        pressed_keys = "";
      }
      pos_Y = text_y.toInt();

      Serial.print("Zrozumialem X: ");
      Serial.print(pos_X);
      Serial.print(" Y: ");
      Serial.print(pos_Y);
      Serial.print(" Keys: ");
      Serial.println(pressed_keys);

      // Handle input
      if (pressed_keys.length() > 0) {
        for (int i = 0; i < pressed_keys.length(); i++) {
          char key = pressed_keys[i];

          // Handle keys
          //TODO: make robot move using this
          if (key == 'p') {
            //Emergency stop
            break;
          } else if (key == 'i') {
            //Go up
          } else if (key == 'k') {
            //Go down
          } else if (key == 'j') {
            //Go left
          } else if (key == 'l') {
            //Go right
          }
        }
      }
    }
  }
}