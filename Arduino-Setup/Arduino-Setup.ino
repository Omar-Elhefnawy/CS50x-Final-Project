const int trigPin = 9;    
const int echoPin = 10;   
const int ledPin = 13;    
const int buzzerPin = 8;  
const long REMINDER_INTERVAL = 3600000; 
const float PRESENCE_THRESHOLD = 50.0;  

long lastReminderTime = 0;
bool isPresent = false;
bool isWaterReminder = true; 

void setup() {
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(ledPin, OUTPUT);   
  pinMode(buzzerPin, OUTPUT); 
  Serial.begin(9600);        
  digitalWrite(ledPin, LOW); 
  digitalWrite(buzzerPin, LOW); 
}

void loop() {
  // Measure distance
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  
  long duration = pulseIn(echoPin, HIGH);
  float distance = duration * 0.034 / 2; 
  
  // Check presence
  bool newPresence = (distance < PRESENCE_THRESHOLD);
  if (newPresence != isPresent) {
    isPresent = newPresence;
    digitalWrite(ledPin, isPresent ? HIGH : LOW); 
    // Send presence status and timestamp
    Serial.print("PRESENCE:");
    Serial.print(isPresent ? "1" : "0");
    Serial.print(",TIME:");
    Serial.println(millis());
  }
  
  // Check for reminders (every hour if present)
  if (isPresent && (millis() - lastReminderTime >= REMINDER_INTERVAL)) {
      
      digitalWrite(buzzerPin, HIGH);
      delay(200);
      digitalWrite(buzzerPin, LOW);
      Serial.println("REMINDER:Drink water!");
    isWaterReminder = !isWaterReminder; 
    lastReminderTime = millis();
  }
  
  delay(1000); 
}