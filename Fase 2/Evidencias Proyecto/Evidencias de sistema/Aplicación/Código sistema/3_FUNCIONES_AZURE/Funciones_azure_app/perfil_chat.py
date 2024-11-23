# perfil_chat.py

import azure.functions as func
import logging
import json
import re
import pyodbc
import os
import time

# Obtener la cadena de conexión desde las variables de entorno
conn_str = os.environ["SqlConnectionString"]

# Función para leer los datos de perfil de empleado en la base de datos
def perfil_usuario(rut, max_retries=3, delay=1):
    """Realiza lectura de perfil de usuario llamando al procedimiento almacenado con reintentos."""
    attempts = 0
    conn = None
    
    try:
        while attempts < max_retries:
            try:
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                cursor.execute("{CALL ObtenerPerfil(?)}", (rut,))
                row = cursor.fetchone()

                if not row or not hasattr(row, 'RUTUsuario'):
                    return False, "Usuario no encontrado", None
                
                perfil = {
                    "NombreCompleto": getattr(row, 'NombreCompleto', "N/A"),
                    "RUTUsuario": getattr(row, 'RUTUsuario', "N/A"),
                    "DV": getattr(row, 'DV', "N/A"),
                    "NumeroTelefono": getattr(row, 'NumeroTelefono', "N/A"),
                    "Email": getattr(row, 'Email', "N/A"),
                    "Edad": getattr(row, 'Edad', "N/A"),
                    "Sexo": getattr(row, 'Sexo', "N/A"),
                    "Ciudad": getattr(row, 'Ciudad', "N/A"),
                    "Nacionalidad": getattr(row, 'Nacionalidad', "N/A"),
                    "Direccion": getattr(row, 'Direccion', "N/A")
                }
                return True, "Usuario encontrado", perfil

            except pyodbc.Error as e:
                attempts += 1
                if attempts == max_retries:
                    return False, f"Error de base de datos: {str(e)}", None
                time.sleep(delay)
                
    finally:
        if conn:
            conn.close()

def main_perfil(req: func.HttpRequest) -> func.HttpResponse:
    """Maneja la solicitud HTTP para el perfil de usuario."""
    try:
        req_body = req.get_json()
        rut = req_body.get('rut')

        if not rut:
            return func.HttpResponse(
                json.dumps({"error": "RUT es requerido"}),
                mimetype="application/json",
                status_code=400
            )

        success, message, perfil = perfil_usuario(rut)

        if success:
            return func.HttpResponse(
                json.dumps({
                    "mensaje": message,
                    **perfil
                }),
                mimetype="application/json",
                status_code=200
            )
        
        return func.HttpResponse(
            json.dumps({"error": message}),
            mimetype="application/json",
            status_code=401
        )

    except (ValueError, KeyError, TypeError) as e:
        return func.HttpResponse(
            json.dumps({"error": "Solicitud inválida: " + str(e)}),
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
