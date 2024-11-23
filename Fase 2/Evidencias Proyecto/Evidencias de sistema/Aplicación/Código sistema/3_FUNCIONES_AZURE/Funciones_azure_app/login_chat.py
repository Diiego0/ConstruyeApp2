# login_chat.py

import azure.functions as func
import logging
import json
import re
import pyodbc
import os
import time
import scrypt
import base64
import jwt

# Configuración
conn_str = os.environ["SqlConnectionString"]
JWT_SECRET = os.environ.get("JWT_SECRET", "fe85ac5165c700310f9cb9e33e748d8802129676b6c66543cf344cd4d4f501ff")

# Validaciones
def validate_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email) is not None

def validate_rut(rut):
    return re.match(r'^\d{1,8}-[0-9kK]$', rut) is not None

def validate_password(password):
    return re.match(r'^(?=.*[a-zA-ZñÑ])(?=.*[A-ZÑ])(?=.*\d)[a-zA-ZñÑ\d]{8,}$', password) is not None

def sanitize_input(input_string):
    return re.sub(r"[;'\"*?=&]", "", input_string.replace(" ", ""))

def clean_rut(rut):
    return rut.split('-')[0]

def generate_token(user_id):
    payload = {
        'user_id': str(user_id),
        'exp': int(time.time()) + (30 * 24 * 60 * 60),  # 30 días
        'iat': int(time.time())
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def login_usuario(identifier, password, max_retries=3, delay=1):
    """Realiza el login del usuario llamando al procedimiento almacenado con reintentos."""
    attempts = 0
    conn = None
    
    try:
        while attempts < max_retries:
            try:
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                cursor.execute("{CALL LoginUsuario(?)}", (identifier,))
                row = cursor.fetchone()

                if not row or not hasattr(row, 'Contraseña'):
                    return False, "Usuario no encontrado", None

                stored_password_bytes = base64.b64decode(row.Contraseña)
                salt = stored_password_bytes[:8]
                stored_hash = stored_password_bytes[8:]
                
                calculated_hash = scrypt.hash(
                    password.encode('utf-8'),
                    salt,
                    N=16384,
                    r=8,
                    p=1,
                    buflen=24
                )
                
                if calculated_hash == stored_hash:
                    user_id = str(row.RUTUsuario) if hasattr(row, 'RUTUsuario') else "1"
                    return True, "Login exitoso", user_id
                return False, "Contraseña incorrecta", None

            except pyodbc.Error as e:
                attempts += 1
                if attempts == max_retries:
                    return False, f"Error de base de datos: {str(e)}", None
                time.sleep(delay)
                
    finally:
        if conn:
            conn.close()

def main_login(req: func.HttpRequest) -> func.HttpResponse:
    """Maneja la solicitud HTTP para el login de usuario."""
    try:
        req_body = req.get_json()
        identifier = req_body.get('identifier')
        password = req_body.get('password')

        if not identifier or not password:
            return func.HttpResponse(
                json.dumps({"error": "Identificador y contraseña son requeridos"}),
                mimetype="application/json",
                status_code=400
            )

        identifier = sanitize_input(identifier)
        password = sanitize_input(password)

        if not (validate_email(identifier) or (validate_rut(identifier) and (identifier := clean_rut(identifier)))):
            return func.HttpResponse(
                json.dumps({"error": "Formato de identificador inválido"}),
                mimetype="application/json",
                status_code=400
            )

        if not validate_password(password):
            return func.HttpResponse(
                json.dumps({"error": "Formato de contraseña inválido"}),
                mimetype="application/json",
                status_code=400
            )

        success, message, user_id = login_usuario(identifier, password)

        if success:
            token = generate_token(user_id)
            return func.HttpResponse(
                json.dumps({
                    "mensaje": message,
                    "token": token,
                    "user_id": user_id
                }),
                mimetype="application/json",
                status_code=200
            )
        
        return func.HttpResponse(
            json.dumps({"error": message}),
            mimetype="application/json",
            status_code=401
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