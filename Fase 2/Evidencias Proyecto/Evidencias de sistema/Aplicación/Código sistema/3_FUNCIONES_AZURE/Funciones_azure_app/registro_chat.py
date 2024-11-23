# registro_chat.py

import azure.functions as func
import logging
import json
import re
import pyodbc
import os
import time
import scrypt
import base64

# Obtener la cadena de conexión desde las variables de entorno
conn_str = os.environ["SqlConnectionString"]

# Funciones de validación y limpieza
def validate_rut(rut):
    """Valida el formato del RUT chileno."""
    pattern = r'^\d{1,8}-[0-9kK]$'
    return re.match(pattern, rut) is not None

def validate_password(password):
    """Valida el formato de la contraseña."""
    pattern = r'^(?=.*[a-zA-ZñÑ])(?=.*[A-ZÑ])(?=.*\d)[a-zA-ZñÑ\d]{8,}$'
    return re.match(pattern, password) is not None

def sanitize_input(input_string):
    """Limpia la entrada de caracteres potencialmente peligrosos."""
    input_string = input_string.replace(" ", "")
    return re.sub(r"[;'\"*?=&]", "", input_string)

def clean_rut(rut):
    """Limpia el RUT eliminando el guión y el dígito verificador."""
    return rut.split('-')[0]

# Función para registrar usuario colaborador en la base de datos
def register_usuario_colaborador(rut, password, direccion, numero, max_retries=3, delay=1):
    """Realiza el registro del usuario llamando al procedimiento almacenado con reintentos."""
    attempts = 0
    while attempts < max_retries:
        try:
            # Generar un salt aleatorio (reducido a 8 bytes)
            salt = os.urandom(8)
            # Generar el hash de la contraseña usando scrypt con buffer más pequeño
            hashed_password = scrypt.hash(
                password.encode('utf-8'),
                salt,
                N=16384,
                r=8,
                p=1,
                buflen=24  # Reducido de 32 a 24
            )
            
            # Combinar salt y hash, y convertir a base64
            final_hash = base64.b64encode(salt + hashed_password).decode('utf-8')

            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            cursor.execute("{CALL RegistrarUsuarioColaborador(?,?,?,?)}", 
                         (rut, final_hash, direccion, numero))
            
            # Verificar si se insertó una fila
            if cursor.rowcount > 0:
                success = True
                message = "Usuario registrado exitosamente."
            else:
                message = cursor.messages[0][1] if cursor.messages else None
                
                if message:
                    success = "exitosamente" in message.lower()
                else:
                    success = False
                    message = "No se pudo registrar el usuario por una razón desconocida."

            conn.commit()
            conn.close()
            return success, message
        except pyodbc.Error as e:
            attempts += 1
            if attempts == max_retries:
                return False, f"Error de base de datos después de {max_retries} intentos: {str(e)}"
            time.sleep(delay)
        except Exception as e:
            return False, str(e)

def main_register(req: func.HttpRequest) -> func.HttpResponse:
    """Maneja la solicitud HTTP para el registro de usuario."""
    logging.info('Función HTTP de Python procesando una solicitud de registro.')

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Cuerpo de solicitud inválido"}),
            mimetype="application/json",
            status_code=400
        )

    # Extraer datos del cuerpo de la solicitud
    rut = req_body.get('rut')
    password = req_body.get('password')
    direccion = req_body.get('direccion')
    numero = req_body.get('numero')

    # Validar campos obligatorios
    if not all([rut, password]):
        return func.HttpResponse(
            json.dumps({"error": "RUT y contraseña son campos obligatorios"}),
            mimetype="application/json",
            status_code=400
        )

    # Sanitizar entradas
    rut = sanitize_input(rut)
    password = sanitize_input(password)

    # Validaciones
    if not validate_rut(rut):
        return func.HttpResponse(
            json.dumps({"error": "Formato de RUT inválido"}),
            mimetype="application/json",
            status_code=400
        )

    if not validate_password(password):
        return func.HttpResponse(
            json.dumps({"error": "Formato de contraseña inválido. La contraseña debe tener al menos 8 caracteres, contener una letra mayúscula, una minúscula y un número."}),
            mimetype="application/json",
            status_code=400
        )

    # Limpiar RUT (solo números, sin guión ni dígito verificador)
    rut_limpio = clean_rut(rut)

    # Registrar usuario colaborador
    success, message = register_usuario_colaborador(rut_limpio, password, direccion, numero)

    if success:
        return func.HttpResponse(
            json.dumps({"mensaje": message}),
            mimetype="application/json",
            status_code=200
        )
    else:
        return func.HttpResponse(
            json.dumps({"error": message}),
            mimetype="application/json",
            status_code=400
        )