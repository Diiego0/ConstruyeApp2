# hijos_chat.py

import azure.functions as func
import logging
import json
import pyodbc
import os
import time

# Obtener la cadena de conexión desde las variables de entorno
conn_str = os.environ["SqlConnectionString"]

def get_hijos(rut, max_retries=3, delay=1):
    """Realiza lectura de hijos del usuario llamando al procedimiento almacenado con reintentos."""
    attempts = 0
    conn = None
    
    try:
        while attempts < max_retries:
            try:
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                cursor.execute("{CALL GetHijos(?)}", (rut,))
                rows = cursor.fetchall()
                
                hijos = []
                for row in rows:
                    # Convertir la fecha a string en formato dd/MM/yyyy
                    fecha_nacimiento = getattr(row, 'FechaNacimientoHijo', None)
                    if fecha_nacimiento:
                        fecha_str = fecha_nacimiento.strftime('%d/%m/%Y')
                    else:
                        fecha_str = "N/A"

                    hijo = {
                        "NombreCompletoHijo": getattr(row, 'NombreCompletoHijo', None),
                        "FechaNacimientoHijo": fecha_str,
                        "EsEstudiante": bool(getattr(row, 'EsEstudiante', None))  # Permitir NULL
                    }
                    hijos.append(hijo)
                
                return True, "Hijos encontrados", hijos

            except pyodbc.Error as e:
                attempts += 1
                if attempts == max_retries:
                    return False, f"Error de base de datos: {str(e)}", None
                time.sleep(delay)
                
    finally:
        if conn:
            conn.close()

def save_hijos(rut, hijos, max_retries=3, delay=1):
    """Guarda los hijos del usuario llamando al procedimiento almacenado con reintentos."""
    attempts = 0
    conn = None
    
    try:
        while attempts < max_retries:
            try:
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                
                for hijo in hijos:
                    # El EsEstudiante puede ser NULL, así que manejamos ese caso
                    es_estudiante = None
                    if 'esEstudiante' in hijo:
                        es_estudiante = 1 if hijo['esEstudiante'] else 0

                    cursor.execute("{CALL RegistrarHijos(?, ?, ?, ?)}", (
                        rut,                           # varchar, not null
                        hijo['nombreCompleto'] or None,# varchar, null
                        hijo['fechaNacimiento'] or None,# date, not null (asumiendo formato dd/MM/yyyy)
                        es_estudiante                  # binary, null
                    ))
                
                conn.commit()
                return True, "Hijos registrados exitosamente", None

            except pyodbc.Error as e:
                attempts += 1
                if attempts == max_retries:
                    return False, f"Error de base de datos: {str(e)}", None
                time.sleep(delay)
                
    finally:
        if conn:
            conn.close()

def main_get_hijos(req: func.HttpRequest) -> func.HttpResponse:
    """Maneja la solicitud HTTP para obtener los hijos del usuario."""
    try:
        req_body = req.get_json()
        rut = req_body.get('rut')

        if not rut:
            return func.HttpResponse(
                json.dumps({"error": "RUT es requerido"}),
                mimetype="application/json",
                status_code=400
            )

        success, message, hijos = get_hijos(rut)

        if success:
            return func.HttpResponse(
                json.dumps({
                    "mensaje": message,
                    "hijos": hijos
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

def main_save_hijos(req: func.HttpRequest) -> func.HttpResponse:
    """Maneja la solicitud HTTP para guardar los hijos del usuario."""
    try:
        req_body = req.get_json()
        rut = req_body.get('rut')
        hijos = req_body.get('hijos')

        if not rut or not hijos:
            return func.HttpResponse(
                json.dumps({"error": "RUT y datos de hijos son requeridos"}),
                mimetype="application/json",
                status_code=400
            )

        success, message, _ = save_hijos(rut, hijos)

        if success:
            return func.HttpResponse(
                json.dumps({
                    "mensaje": message
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