// 217000981 JJ PETERS - Assignment 4 - Smart Room Controller

#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include "driver/ledc.h"  // Required for ledc_channel_config on ESP32-C3

// WiFi credentials and token
const char* ssid = "Binary Core";
const char* password = "ondz10101";
const char* authToken = "1234567";  // Replace with real token

// Pin Definitions
const int pirPin = 3;
const int ldrPin = 1;
const int potPin = 0;
const int fanPin = 7;
const int lightPin = 6;
const int ledPin = 8;
// PWM settings
const int pwmChannel = 0;
const int pwmFreq = 5000;
const int pwmResolution = 8;

bool lightState = false;
bool ldrState = true;
int fanSpeed = 0;

WebServer server(80);

void setup() {
  Serial.begin(115200);

  pinMode(pirPin, INPUT);
  pinMode(lightPin, OUTPUT);
   pinMode(fanPin, OUTPUT);
   pinMode(ledPin, OUTPUT);

  // PWM config
  ledc_timer_config_t ledc_timer = {
    .speed_mode = LEDC_LOW_SPEED_MODE,
    .duty_resolution = (ledc_timer_bit_t)pwmResolution,
    .timer_num = LEDC_TIMER_0,
    .freq_hz = pwmFreq,
    .clk_cfg = LEDC_AUTO_CLK
  };
  ledc_timer_config(&ledc_timer);

  ledc_channel_config_t ledc_channel = {
    .gpio_num = fanPin,
    .speed_mode = LEDC_LOW_SPEED_MODE,
    .channel = (ledc_channel_t)pwmChannel,
    .intr_type = LEDC_INTR_DISABLE,
    .timer_sel = LEDC_TIMER_0,
    .duty = 0,
    .hpoint = 0
  };
  ledc_channel_config(&ledc_channel);

  // WiFi
  WiFi.begin(ssid, password);
  delay(9000);
  //while (WiFi.status() != WL_CONNECTED) {
    //delay(500);
    //Serial.print(".");
//  }
  Serial.println("\nConnected! IP:");
  Serial.println(WiFi.localIP());

  // Routes
  server.on("/sensors", HTTP_GET, handleSensors);
  server.on("/set_fan", HTTP_POST, handleSetFan);
  server.on("/toggle_light", HTTP_POST, handleToggleLight);
  server.on("/toggle_ldr", HTTP_POST, handleToggleLDR);

  server.begin();
}

void loop() {
  server.handleClient();

  // Potentiometer controls fan
  fanSpeed = analogRead(potPin) / 16;  // Convert 0–4095 to ~0–255

  // LDR controls light (adjusted logic: ON if dark)
  if (ldrState) {
    int ldrValue = analogRead(ldrPin);
    lightState = ldrValue >= 2000;  // ON if dark, OFF if bright
    digitalWrite(lightPin, lightState ? HIGH : LOW);  // Turn ON light when dark
  }

  

  ledc_set_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)pwmChannel, fanSpeed);
  ledc_update_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)pwmChannel);
  analogWrite(fanPin,fanSpeed);
  analogWrite(ledPin,fanSpeed);

  // Serial Monitor Logging
  Serial.println("=== Sensor Status ===");
  Serial.print("PIR: ");
  Serial.println(digitalRead(pirPin) == HIGH ? "Person Detected" : "Not Detected");
  Serial.print("LDR: ");
  Serial.println(analogRead(ldrPin));
  Serial.print("Potentiometer: ");
  Serial.println(analogRead(potPin));
  Serial.print("Fan PWM: ");
  Serial.println(fanSpeed);
  Serial.print("Light State: ");
  Serial.println(lightState ? "OFF" : "ON");
  Serial.println("======================");

  delay(1000);
}



void handleSensors() {
  StaticJsonDocument<256> doc;

  int pirRaw = digitalRead(pirPin);
  const char* pirStatus = pirRaw == HIGH ? "Person Detected" : "Not Detected";

  int ldrVal = analogRead(ldrPin);
  int potVal = analogRead(potPin);

  doc["pir"] = pirStatus;
  doc["ldr"] = ldrVal;
  doc["pot"] = potVal;
  doc["fan_pwm"] = fanSpeed;
  doc["light_state"] = lightState;

  Serial.println("=== Sensor Status ===");
  Serial.print("PIR: ");
  Serial.println(pirStatus);
  Serial.print("LDR: ");
  Serial.println(ldrVal);
  Serial.print("Potentiometer: ");
  Serial.println(potVal);
  Serial.print("Fan PWM: ");
  Serial.println(fanSpeed);
  Serial.print("Light State: ");
  Serial.println(lightState ? "OFF" : "ON");
  Serial.println("======================");

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handleSetFan() {
  if (!server.authenticate(authToken, "")) {
    return server.requestAuthentication();
  }

  if (server.hasArg("plain")) {
    StaticJsonDocument<200> doc;
    deserializeJson(doc, server.arg("plain"));
    fanSpeed = constrain(doc["fan_speed"], 0, 255);
    server.send(200, "application/json", "{\"status\":\"OK\"}");
  } else {
    server.send(400, "application/json", "{\"error\":\"No data\"}");
  }
}

void handleToggleLight() {
  if (!server.authenticate(authToken, "")) {
    return server.requestAuthentication();
  }

  if (server.hasArg("plain")) {
    StaticJsonDocument<200> doc;
    deserializeJson(doc, server.arg("plain"));
    lightState = doc["state"];
    digitalWrite(lightPin, lightState ? HIGH : LOW);
    server.send(200, "application/json", "{\"status\":\"OK\"}");
  } else {
    server.send(400, "application/json", "{\"error\":\"No data\"}");
  }
}

void handleToggleLDR() {
  if (!server.authenticate(authToken, "")) {
    return server.requestAuthentication();
  }

  ldrState = !ldrState;
  String response = ldrState ? "{\"status\":\"LDR OFF\"}" : "{\"status\":\"LDR ON\"}";
  server.send(200, "application/json", response);
}
