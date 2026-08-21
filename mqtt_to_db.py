import paho.mqtt.client as mqtt
import psycopg2
import json

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "postgres",
    "user": "postgres",
    "password": "guclu_bir_sifre123"  # docker run'da verdiğin şifreyle aynı olmalı
}

MQTT_BROKER = "127.0.0.1"
MQTT_TOPIC = "powermeter/anl13/live"

conn = psycopg2.connect(**DB_CONFIG)
conn.autocommit = True
cur = conn.cursor()

def on_connect(client, userdata, flags, rc, properties=None):
    print("MQTT broker'a baglanildi, rc:", rc)
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        cur.execute("""
            INSERT INTO measurements
            (device_id, v1, i1, p1, f1, v2, i2, p2, v3, i3, p3, vL12, vL23, vL31)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            "anl13_01",
            data.get("v1"), data.get("i1"), data.get("p1"), data.get("f1"),
            data.get("v2"), data.get("i2"), data.get("p2"),
            data.get("v3"), data.get("i3"), data.get("p3"),
            data.get("vL12"), data.get("vL23"), data.get("vL31")
        ))
        print("Veri yazildi:", data)
    except Exception as e:
        print("Hata:", e)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, 1883, 60)
client.loop_forever()