"""Lector NFC: lee el UID de la tarjeta por puerto serial y avisa a Flask.

Correcciones frente a la version anterior (main.py):
- Antes, si el puerto serial no existia, el proceso moria y nadie se
  enteraba (Flask seguia corriendo sin lector). Ahora reintenta la
  conexion cada 5 segundos y registra cada intento en el log.
- Acepta dos formatos de lectura: el UID en texto plano (una linea,
  como lo manda un lector USB) o un JSON {"nfc_id": "..."} (como lo
  puede mandar un ESP32 con ArduinoJson).
- Si se definio LECTOR_CLAVE en .env, la envia como cabecera
  X-Lector-Clave (la app la exige en /api/retiro-nfc).

Se ejecuta como servicio propio (compose.lector.yaml), no dentro del
contenedor de la app.
"""
import json
import os
import time

import requests
import serial

PUERTO = os.environ.get("SERIAL_PORT", "/dev/ttyUSB0")
BAUDIOS = int(os.environ.get("SERIAL_BAUD", "115200"))
API_URL = os.environ.get("API_URL", "http://app:5000").rstrip("/")
LECTOR_CLAVE = os.environ.get("LECTOR_CLAVE", "")

URL_RETIRO = f"{API_URL}/api/retiro-nfc"
ESPERA_RECONEXION = 5  # segundos entre reintentos del puerto serial


def extraer_nfc_id(linea):
    """Devuelve el NFC ID de una linea: JSON {"nfc_id": ...} o texto."""
    linea = linea.strip()
    if not linea:
        return None
    if linea.startswith("{"):
        try:
            datos = json.loads(linea)
            for clave in ("nfc_id", "uid", "id", "tarjeta"):
                if datos.get(clave):
                    return str(datos[clave]).strip().upper()
        except ValueError:
            pass
        return None
    return linea.upper()


def enviar_retiro(nfc_id):
    cabeceras = {}
    if LECTOR_CLAVE:
        cabeceras["X-Lector-Clave"] = LECTOR_CLAVE
    respuesta = requests.post(
        URL_RETIRO, json={"nfc_id": nfc_id}, headers=cabeceras, timeout=5
    )
    resultado = respuesta.json()
    if respuesta.status_code == 200:
        print("RETIRO EXITOSO")
        print("Empleado:", resultado["empleado"])
        print("Pedidos retirados:", resultado["pedidos_retirados"])
    else:
        print("RETIRO NO REALIZADO")
        print(resultado.get("error"))


def escuchar_puerto():
    print(f"Conectando al lector en {PUERTO} ({BAUDIOS} baudios)...")
    with serial.Serial(PUERTO, BAUDIOS, timeout=1) as ser:
        print("Lector conectado. Esperando tarjetas...")
        while True:
            linea = ser.readline().decode("ascii", errors="ignore").strip()
            nfc_id = extraer_nfc_id(linea)
            if not nfc_id:
                continue
            print("NFC detectado:", nfc_id)
            try:
                enviar_retiro(nfc_id)
            except requests.RequestException as error:
                print("Error al conectar con Flask:", error)


def main():
    print("Lector NFC iniciado.")
    print(f"API: {URL_RETIRO}")
    while True:
        try:
            escuchar_puerto()
        except serial.SerialException as error:
            print(f"Error con el sensor NFC: {error}")
            print(f"Reintentando en {ESPERA_RECONEXION} s... "
                  "(revisa el cable USB y el puerto)")
            time.sleep(ESPERA_RECONEXION)
        except KeyboardInterrupt:
            print("Lector NFC detenido.")
            break


if __name__ == "__main__":
    main()
