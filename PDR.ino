	Arduino Code:
#include <Wire.h>



// MPU6050 I2C address and register definitions
#define MPU6050_ADDR 0x68
#define PWR_MGMT_1 0x6B
#define ACCEL_XOUT_H 0x3B
#define GYRO_CONFIG 0x1B
#define ACCEL_CONFIG 0x1C
#define CONFIG 0x1A

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  
  // Start I2C communication
  Wire.begin();
  Wire.setClock(400000);  // Set I2C to 400kHz for faster communication
  delay(100);
  
  // Wake up the MPU6050 (it starts in sleep mode by default)
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(PWR_MGMT_1);
  Wire.write(0x00);  // Write 0 to wake it up
  if (Wire.endTransmission() != 0) {
    Serial.println("{\"error\":\"sensor_not_found\"}");
    while(1) delay(1000);  // Stop here if sensor isn't connected
  }
  delay(100);
  
  // Set gyroscope range to ±500°/s
  // This gives us enough range for normal walking/running
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(GYRO_CONFIG);
  Wire.write(0x08);  // 0x08 = ±500°/s range
  Wire.endTransmission();
  
  // Set accelerometer range to ±4g
  // Good balance between sensitivity and range for PDR
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(ACCEL_CONFIG);
  Wire.write(0x08);  // 0x08 = ±4g range
  Wire.endTransmission();
  
  // Set low-pass filter to 21Hz bandwidth
  // Helps reduce noise from vibrations and high-frequency junk
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(CONFIG);
  Wire.write(0x04);  // 0x04 = 21Hz DLPF
  Wire.endTransmission();
  
  delay(100);
  
  Serial.println("{\"status\":\"sensor_ready\"}");
}

void loop() {
  // Read all sensor data in one go (more efficient than reading separately)
  // Order: accel X,Y,Z (6 bytes) + temp (2 bytes) + gyro X,Y,Z (6 bytes) = 14 bytes total
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(ACCEL_XOUT_H);  // Start reading from accel register
  Wire.endTransmission(false);
  Wire.requestFrom(MPU6050_ADDR, 14);
  
  if (Wire.available() >= 14) {
    // Read raw 16-bit values from sensor
    int16_t ax_raw = (Wire.read() << 8) | Wire.read();
    int16_t ay_raw = (Wire.read() << 8) | Wire.read();
    int16_t az_raw = (Wire.read() << 8) | Wire.read();
    Wire.read(); Wire.read();  // Skip temperature readings (don't need them)
    int16_t gx_raw = (Wire.read() << 8) | Wire.read();
    int16_t gy_raw = (Wire.read() << 8) | Wire.read();
    int16_t gz_raw = (Wire.read() << 8) | Wire.read();
    
    // Convert raw sensor values to real units (m/s² for accel, rad/s for gyro)
    
    // Accelerometer conversion:
    // ±4g range means sensitivity is 8192 LSB/g
    // To convert to m/s²: (raw / 8192) * 9.81 = raw * (9.81/8192) = raw * 0.0011978149
    float ax = ax_raw * 0.0011978149;
    float ay = ay_raw * 0.0011978149;
    float az = az_raw * 0.0011978149;
    
    // Gyroscope conversion:
    // ±500°/s range means sensitivity is 65.5 LSB/(°/s)
    // To convert to rad/s: (raw / 65.5) * (π/180) = raw * 0.0002663309
    float gx = gx_raw * 0.0002663309;
    float gy = gy_raw * 0.0002663309;
