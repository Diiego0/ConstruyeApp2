# password_retry_sms.py

import azure.functions as func
import logging
import json
import re
import pyodbc
import os
import time
import random
from azure.communication.sms import SmsClient

# Configuración
conn_str = os.environ["SqlConnectionString"]
#Reemplaza "tu_connection_string_de_communication_services" con el connection string real de Azure Communication Services
COMMUNICATION_CONNECTION_STRING = os.environ.get("CommunicationServicesConnectionString", "tu_connection_string_de_communication_services")
#Reemplaza "+tu_numero_de_sender" con el número de teléfono real que obtuviste de Azure Communication Services
SMS_FROM_NUMBER = os.environ.get("SmsFromNumber", "+tu_numero_de_sender")

def validate_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email) is not None

def validate_rut(rut):
    return re.match(r'^\d{1,8}-[0-9kK]$', rut) is not None

def sanitize_input(input_string):
    return re.sub(r"[;'\"*?=&]", "", input_string.replace(" ", ""))

def clean_rut(rut):
    return rut.split('-')[0]

def generate_code():
    """Genera un código de 6 dígitos."""
    return str(random.randint(100000, 999999))

def get_user_phone(identifier, max_retries=3, delay=1):
    """Obtiene el número de teléfono del usuario."""
    attempts = 0
    conn = None
    
    try:
        while attempts < max_retries:
            try:
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                cursor.execute("{CALL GetUserPhone(?)}", (identifier,))
                row = cursor.fetchone()

                if not row:
                    return None, "Usuario no encontrado"

                phone = row.Telefono if hasattr(row, 'Telefono') else None
                if not phone:
                    return None, "Usuario no tiene teléfono registrado"

                return phone, "Teléfono encontrado"

            except pyodbc.Error as e:
                attempts += 1
                if attempts == max_retries:
                    return None, f"Error de base de datos: {str(e)}"
                time.sleep(delay)
    finally:
        if conn:
            conn.close()

def save_reset_code(identifier, code, phone, max_retries=3, delay=1):
    """Guarda el código de recuperación en la base de datos."""
    attempts = 0
    conn = None
    
    try:
        while attempts < max_retries:
            try:
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                expiration = time.time() + (15 * 60)  # 15 minutos de validez
                
                cursor.execute(
                    "{CALL SaveResetCode (?, ?, ?, ?)}",
                    (identifier, code, phone, expiration)
                )
                conn.commit()
                return True, "Código guardado exitosamente"

            except pyodbc.Error as e:
                attempts += 1
                if attempts == max_retries:
                    return False, f"Error al guardar código: {str(e)}"
                time.sleep(delay)
    finally:
        if conn:
            conn.close()

def send_sms(phone_number, code):
    """Envía el SMS usando Azure Communication Services."""
    try:
        sms_client = SmsClient.from_connection_string(COMMUNICATION_CONNECTION_STRING)
        response = sms_client.send(
            from_=SMS_FROM_NUMBER,
            to=phone_number,
            message=f"Tu código de recuperación de contraseña es: {code}"
        )
        return True, "SMS enviado exitosamente"
    except Exception as e:
        logging.error(f"Error enviando SMS: {str(e)}")
        return False, f"Error al enviar SMS: {str(e)}"

def main_password_retry(req: func.HttpRequest) -> func.HttpResponse:
    """Maneja la solicitud HTTP para la recuperación de contraseña."""
    try:
        req_body = req.get_json()
        identifier = req_body.get('identifier')

        if not identifier:
            return func.HttpResponse(
                json.dumps({"error": "Identificador es requerido"}),
                mimetype="application/json",
                status_code=400
            )

        identifier = sanitize_input(identifier)

        if not (validate_email(identifier) or (validate_rut(identifier) and (identifier := clean_rut(identifier)))):
            return func.HttpResponse(
                json.dumps({"error": "Formato de identificador inválido"}),
                mimetype="application/json",
                status_code=400
            )

        # Obtener teléfono del usuario
        phone, message = get_user_phone(identifier)
        if not phone:
            return func.HttpResponse(
                json.dumps({"error": message}),
                mimetype="application/json",
                status_code=404
            )

        # Generar código
        code = generate_code()

        # Guardar código en la base de datos
        success, db_message = save_reset_code(identifier, code, phone)
        if not success:
            return func.HttpResponse(
                json.dumps({"error": db_message}),
                mimetype="application/json",
                status_code=500
            )

        # Enviar SMS
        sms_success, sms_message = send_sms(phone, code)
        if not sms_success:
            return func.HttpResponse(
                json.dumps({"error": sms_message}),
                mimetype="application/json",
                status_code=500
            )

        # Enmascarar el número de teléfono
        masked_phone = f"****{phone[-4:]}"

        return func.HttpResponse(
            json.dumps({
                "mensaje": "Código enviado exitosamente",
                "phone": masked_phone
            }),
            mimetype="application/json",
            status_code=200
        )

    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Cuerpo de solicitud inválido"}),
            mimetype="application/json",
            status_code=400
        )
    except Exception as e:
        logging.error(f"Error no manejado: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": "Error interno del servidor"}),
            mimetype="application/json",
            status_code=500
        )