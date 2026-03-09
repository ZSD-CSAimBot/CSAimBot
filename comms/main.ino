int pos_X = 0;
int pos_Y = 0;

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(10);
}

void loop() {
  if (Serial.available() > 0) {

    String data = Serial.readStringUntil('\r');
    data.trim();

    int comma_idx = data.indexOf(',');

    if (comma_idx > 0) {

      String text_x = data.substring(0, comma_idx);
      pos_X = text_x.toInt();

      String text_y = data.substring(comma_idx + 1);
      pos_Y = text_y.toInt();

      Serial.print("Zrozumialem X: "); Serial.print(pos_X);
      Serial.print(" oraz Y: "); Serial.println(pos_Y);
    }
  }
}