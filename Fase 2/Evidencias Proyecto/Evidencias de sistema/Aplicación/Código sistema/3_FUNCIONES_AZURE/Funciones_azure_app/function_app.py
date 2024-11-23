# function_app.py

import azure.functions as func
import datetime
import json
import logging
import login_chat
import registro_chat
import perfil_chat
import hijos_chat
import password_retry_sms

app = func.FunctionApp()

@app.route(route="http_trigger_login", auth_level=func.AuthLevel.FUNCTION)
def http_trigger_login(req: func.HttpRequest) -> func.HttpResponse:
    return login_chat.main_login(req)

@app.route(route="http_trigger_registro", auth_level=func.AuthLevel.FUNCTION)
def http_trigger_registro(req: func.HttpRequest) -> func.HttpResponse:
    return registro_chat.main_register(req)

@app.route(route="http_trigger_perfil", auth_level=func.AuthLevel.FUNCTION)
def http_trigger_perfil(req: func.HttpRequest) -> func.HttpResponse:
    return perfil_chat.main_perfil(req)

@app.route(route="http_trigger_get_hijos", auth_level=func.AuthLevel.FUNCTION)
def http_trigger_get_hijos(req: func.HttpRequest) -> func.HttpResponse:
    return hijos_chat.main_get_hijos(req)

@app.route(route="http_trigger_save_hijos", auth_level=func.AuthLevel.FUNCTION)
def http_trigger_save_hijos(req: func.HttpRequest) -> func.HttpResponse:
    return hijos_chat.main_save_hijos(req)


@app.route(route="http_trigger_password_retry_sms", auth_level=func.AuthLevel.FUNCTION)
def http_trigger_password_retry_sms(req: func.HttpRequest) -> func.HttpResponse:
    return password_retry_sms.main_password_retry(req)