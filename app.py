# app.py
import os
from dotenv import load_dotenv
load_dotenv()
import json
from datetime import datetime, date, timedelta
from supabase import create_client, Client
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
import uuid
import calendar
import base64
import traceback

# Importaciones para notificaciones push
from pywebpush import WebPushException, webpush 
import pywebpush

# Importaciones para programar tareas
from flask_apscheduler import APScheduler

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secreto_y_cambiar_en_produccion")
CORS(app)

# !IMPORTANTE!: Reemplaza "TU_SUPABASE_URL_AQUI" y "TU_SUPABASE_KEY_AQUI"
# con los valores reales de tu proyecto Supabase.
# Es preferible usar variables de entorno en producción.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ugpqqmcstqtywyrzfnjq.supabase.co")
# IMPORTANTE: Asegúrate de reemplazar esta clave con tu clave real de Supabase.
# Puedes encontrarla en la configuración de tu proyecto Supabase (API Settings).\
# Utiliza la 'anon public' key o 'service_role' key (¡con precaución!).
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVncHFxbWNzdHF0eXd5cnpmbmpxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk3Mzk2ODgsImV4cCI6MjA2NTMxNTY4OH0.nh56rQQliOnX5AZzePaZv_RB05uRIlUbfQPkWJPvKcE") # <--- ¡ACTUALIZA ESTA LÍNEA CON TU CLAVE REAL!

supabase: Client = None

# Verifica si las variables de entorno están configuradas. Si no, imprime un error y sale.
if not SUPABASE_URL or not SUPABASE_KEY:
    print("[ERROR] Fallo crítico: Las variables de entorno SUPABASE_URL y SUPABASE_KEY no están configuradas.")
    print("[ERROR] Asegúrate de definirlas en tu entorno de despliegue (ej., Render) o localmente.")
else:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase conectado y cliente inicializado correctamente.")
    except Exception as e:
        print(f"[ERROR] Fallo crítico al conectar o inicializar Supabase: {e}")
        supabase = None

# VAPID Key Management para notificaciones Push
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY")
# IMPORTANTE: Reemplaza "mailto:your_email@example.com" con un correo electrónico real
# Este correo se utiliza para identificar al remitente de las notificaciones en caso de abuso.
VAPID_CLAIMS = {"sub": "mailto:your_email@example.com"}

# NUEVO: Generar claves VAPID si no existen
if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
    print("[INFO] Generando nuevas claves VAPID ya que no se encontraron en las variables de entorno...")
    vapid_keys = pywebpush.generate_vapid_keys()
    VAPID_PRIVATE_KEY = vapid_keys['private_key']
    VAPID_PUBLIC_KEY = vapid_keys['public_key']
    print(f"[INFO] Nuevas VAPID_PUBLIC_KEY generada: {VAPID_PUBLIC_KEY}")
    print(f"[INFO] Nuevas VAPID_PRIVATE_KEY generada: {VAPID_PRIVATE_KEY}")
    print("[INFO] ^^^ Por favor, copia estas claves y guárdalas en tu archivo .env o en tus variables de entorno de producción. ^^^")
else:
    print("[INFO] Usando claves VAPID existentes desde las variables de entorno.")

# Inicializar APScheduler
scheduler = APScheduler()

# Nota: El decorador login_required es un placeholder si no hay un sistema de autenticación real.
# Se ha movido la importación de 'wraps' dentro de la función para evitar errores de importación circular.
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Implementa aquí tu lógica de autenticación real si es necesario
        return f(*args, **kwargs)
    return decorated_function

def init_db_supabase():
    if supabase is None:
        print("[WARNING] Supabase no está inicializado. No se pueden insertar tipos de registro/documento predeterminados.")
        return

    try:
        response = supabase.from_('tipo_registro').select('count', count='exact').execute()
        count_registro = response.count
        if count_registro == 0:
            print("Insertando tipos de registro predeterminados en Supabase...")
            default_types_registro = [
                {"nombre": "General"}, {"nombre": "Salud"}, {"nombre": "Cita"},
                {"nombre": "Escolar"}, {"nombre": "Personal"}, {"nombre": "Finanzas"},
                {"nombre": "Documento"}, {"nombre": "Trabajo"}, {"nombre": "Hogar"},
                {"nombre": "Ocio"}, {"nombre": "Deporte"}, {"nombre": "Emergencia"}
            ]
            supabase.from_('tipo_registro').insert(default_types_registro).execute()
            print(f"Tipos de registro predeterminados insertados: {len(default_types_registro)}.")
        else:
            print(f"La tabla 'tipo_registro' ya contiene {count_registro} datos.")
    except Exception as e:
        print(f"[ERROR] Error al inicializar/insertar tipos de registro en Supabase: {e}")

    try:
        response = supabase.from_('tipo_documento').select('count', count='exact').execute()
        count_documento = response.count
        if count_documento == 0:
            print("Insertando tipos de documento predeterminados en Supabase...")
            default_types_documento = [
                {"nombre": "Factura"}, {"nombre": "Contrato"}, {"nombre": "Recibo"},
                {"nombre": "Garantía"}, {"nombre": "Manual"}, {"nombre": "Identificación"},
                {"nombre": "Acuerdo"}, {"nombre": "Educación"}, {"nombre": "Salud"},
                {"nombre": "Vehículo"}, {"nombre": "Propiedad"}, {"nombre": "Otro"}
            ]
            supabase.from_('tipo_documento').insert(default_types_documento).execute()
            print(f"Tipos de documento predeterminados insertados: {len(default_types_documento)}.")
        else:
            print(f"La tabla 'tipo_documento' ya contiene {count_documento} datos.")
    except Exception as e:
        print(f"[ERROR] Error al inicializar/insertar tipos de documento en Supabase: {e}")

def generate_tasks_for_today_from_routines():
    """Genera tareas de rutina para hoy basadas en las rutinas definidas."""
    if supabase is None:
        print("[WARNING] Supabase no está inicializado. No se pueden generar tareas a partir de rutinas.")
        return

    today_date_str = datetime.now().strftime('%Y-%m-%d')
    today_date_obj = datetime.now().date()
    today_day_of_week_py = datetime.now().weekday()
    today_day_of_week_html_format = (today_day_of_week_py + 1) % 7

    print(f"[{datetime.now()}] Intentando generar tareas para hoy ({today_date_str}, día de la semana HTML: {today_day_of_week_html_format}) a partir de las rutinas.")

    try:
        settings_response = supabase.from_('app_settings').select('last_task_generation_date').limit(1).execute()
        last_generation_date_str = settings_response.data[0]['last_task_generation_date'] if settings_response.data else None

        last_generation_date_obj = None
        if last_generation_date_str:
            try:
                last_generation_date_obj = datetime.strptime(last_generation_date_str, '%Y-%m-%d').date()
            except ValueError:
                print(f"[WARNING] Formato de fecha inválido en last_task_generation_date: {last_generation_date_str}. Se forzará la regeneración.")
                last_generation_date_obj = None

        if last_generation_date_obj == today_date_obj:
            print(f"[{datetime.now()}] Las tareas para hoy ({today_date_str}) ya fueron generadas previamente. Saltando generación.")
            return

        print(f"[{datetime.now()}] Generando tareas para hoy ({today_date_str})...")

        response = supabase.from_('rutina').select('id,nombre,hora,dias_semana').execute()
        routines = response.data

        for routine in routines:
            routine_id = routine['id']
            routine_name = routine['nombre']
            routine_time = routine['hora']
            dias_semana_raw = routine['dias_semana']

            routine_days = []
            if dias_semana_raw:
                try:
                    routine_days = json.loads(dias_semana_raw)
                    if not isinstance(routine_days, list):
                        routine_days = []
                except (json.JSONDecodeError, TypeError):
                    print(f"Error: No se pudo decodificar dias_semana para la rutina {routine_id}: {dias_semana_raw}. Saltando esta rutina.")
                    continue

            if today_day_of_week_html_format in routine_days:
                existing_task_response = supabase.from_('tarea').select('id').eq('fecha', today_date_str).eq('texto', routine_name).eq('hora', routine_time).execute()
                existing_task = existing_task_response.data

                if not existing_task:
                    new_task_data = {
                        'fecha': today_date_str,
                        'texto': routine_name,
                        'hora': routine_time,
                        'completada': False,
                        'notified': False # Nuevo campo para notificaciones programadas
                    }
                    insert_response = supabase.from_('tarea').insert(new_task_data).execute()
                    if insert_response.data:
                        print(f"[{datetime.now()}] Tarea '{routine_name}' generada para hoy a partir de la rutina {routine_id}. ID: {insert_response.data[0]['id']}.")
                    else:
                        print(f"[{datetime.now()}] Fallo al generar la tarea '{routine_name}' para hoy a partir de la rutina {routine_id}.")

        if settings_response.data:
            supabase.from_('app_settings').update({'last_task_generation_date': today_date_str}).eq('id', settings_response.data[0]['id']).execute()
        else:
            supabase.from_('app_settings').insert({'last_task_generation_date': today_date_str}).execute()

        print(f"[{datetime.now()}] Generación de tareas a partir de rutinas finalizada y fecha de última generación actualizada a {today_date_str}.")

    except Exception as e:
        print(f"[ERROR] Error en generate_tasks_for_today_from_routines: {e}")

def manage_overdue_tasks():
    """Gestiona tareas atrasadas (elimina completadas, mueve incompletas a hoy)."""
    if supabase is None:
        print("[WARNING] Supabase no está inicializado. No se pueden gestionar tareas atrasadas.")
        return

    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f"[{datetime.now()}] Iniciando la gestión de tareas atrasadas para el día: {today_str}")

    try:
        delete_response = supabase.from_('tarea').delete().lt('fecha', today_str).eq('completada', True).execute()
        deleted_count = len(delete_response.data) if delete_response.data else 0
        print(f"[{datetime.now()}] Eliminadas {deleted_count} tareas completadas de días anteriores.")

        update_response = supabase.from_('tarea').update({'fecha': today_str}).lt('fecha', today_str).eq('completada', False).execute()
        moved_count = len(update_response.data) if update_response.data else 0
        print(f"[{datetime.now()}] Movidas {moved_count} tareas incompletas de días anteriores al día actual.")

        print(f"[{datetime.now()}] Gestión de tareas atrasadas finalizada.")
    except Exception as e:
        print(f"[ERROR] Error en manage_overdue_tasks: {e}")

# NUEVO: Función para enviar notificaciones push a todos los suscriptores
def _send_push_notification_to_all(title, body, icon='/static/icons/notification-icon.png'):
    if supabase is None:
        print("[ERROR] Supabase no está inicializado. No se pueden enviar notificaciones push.")
        return 0, 0, []

    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        print("[ERROR] Claves VAPID no configuradas en el servidor. No se pueden enviar notificaciones.")
        return 0, 0, []

    try:
        subscriptions_response = supabase.from_('push_subscriptions').select('*').execute()
        subscriptions = subscriptions_response.data

        if not subscriptions:
            print("[INFO] No hay suscriptores para enviar notificaciones.")
            return 0, 0, []

        successful_sends = 0
        failed_sends = 0
        invalid_subscriptions = []

        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub['endpoint'],
                        "keys": {
                            "p256dh": sub['p256dh'],
                            "auth": sub['auth']
                        }
                    },
                    data=json.dumps({
                        "title": title,
                        "body": body,
                        "icon": icon
                    }),
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS
                )
                successful_sends += 1
            except WebPushException as e:
                print(f"Error al enviar push a {sub['endpoint']}: {e}")
                if e.response.status_code in [404, 410]: # Not Found (404), Gone (410) - La suscripción ya no es válida
                    invalid_subscriptions.append(sub['id'])
                failed_sends += 1
            except Exception as e:
                print(f"Error inesperado al enviar push a {sub['endpoint']}: {e}")
                traceback.print_exc()
                failed_sends += 1

        if invalid_subscriptions:
            supabase.from_('push_subscriptions').delete().in_('id', invalid_subscriptions).execute()
            print(f"Eliminadas {len(invalid_subscriptions)} suscripciones inválidas.")

        return successful_sends, failed_sends, invalid_subscriptions
    except Exception as e:
        print(f"Error al recuperar suscripciones o al enviar notificaciones en masa: {e}")
        traceback.print_exc()
        return 0, 0, []

# NUEVO: Tarea programada para verificar y enviar notificaciones de tareas y citas
@scheduler.task('interval', id='check_and_send_notifications', minutes=1, misfire_grace_time=900)
def check_and_send_notifications_job():
    with app.app_context(): # Es necesario si accedes a recursos de Flask como 'supabase'
        print(f"[{datetime.now()}] Ejecutando la tarea programada: check_and_send_notifications")
        if supabase is None:
            print("[WARNING] Supabase no está inicializado en la tarea programada. Saltando.")
            return

        current_datetime = datetime.now()
        # Rango de tiempo para buscar tareas/citas (ej. los próximos 2 minutos, para dar margen)
        notification_window_start = current_datetime - timedelta(seconds=30) # Un poco hacia atrás por si se pasó
        notification_window_end = current_datetime + timedelta(minutes=2, seconds=30) # Para capturar lo que está a punto de ocurrir

        print(f"[DEBUG_TIME] Current server time: {current_datetime}")
        print(f"[DEBUG_TIME] Notification window: {notification_window_start} to {notification_window_end}")


        # --- Notificaciones para Tareas ---
        try:
            # DEBUG: Imprimir la consulta y los filtros antes de ejecutar
            print(f"[DEBUG_DB] Querying 'tarea' with conditions: completada=False, notified=False (hora filter handled in Python)")
            tasks_to_notify_response = supabase.from_('tarea').select('id,texto,fecha,hora') \
                                            .eq('completada', False) \
                                            .eq('notified', False) \
                                            .execute()
            
            tasks_to_notify = tasks_to_notify_response.data
            # DEBUG: Imprimir los datos recuperados
            print(f"[DEBUG_DB] Raw tasks retrieved: {tasks_to_notify}")
            
            for task in tasks_to_notify:
                # IMPORTANT: Handle None or "None" string values for 'hora' explicitly in Python
                if not task['hora'] or str(task['hora']).lower() == 'none':
                    print(f"[DEBUG_TASK] Skipping task {task['id']} due to invalid or missing hora: '{task['hora']}'")
                    continue

                # DEBUG: Imprimir los datos de la tarea antes de la conversión de fecha/hora
                print(f"[DEBUG_TASK] Processing task: ID={task['id']}, Fecha={task['fecha']}, Hora={task['hora']}")
                task_datetime_str = f"{task['fecha']} {task['hora']}"
                try:
                    # UPDATED: Changed from '%H:%M' to '%H:%M:%S' to correctly parse time with seconds
                    task_full_datetime = datetime.strptime(task_datetime_str, '%Y-%m-%d %H:%M:%S') 
                    notify_time = task_full_datetime - timedelta(minutes=15) # Notificar 15 minutos antes

                    print(f"[DEBUG_TIME] Task '{task['texto']}' (ID: {task['id']}) - Task time: {task_full_datetime}, Notify time: {notify_time}")

                    if notification_window_start <= notify_time <= notification_window_end:
                        print(f"[INFO] Preparando notificación para tarea: {task['texto']} a las {task['hora']} del {task['fecha']}")
                        title = "Recordatorio de Tarea"
                        body = f"¡Faltan 15 minutos para: {task['texto']} a las {task['hora']}!"
                        
                        successful, failed, invalid = _send_push_notification_to_all(title, body)
                        print(f"[INFO] Notificación enviada para tarea '{task['texto']}'. Éxito: {successful}, Fallo: {failed}")

                        if successful > 0: 
                            supabase.from_('tarea').update({'notified': True}).eq('id', task['id']).execute()
                            print(f"[INFO] Tarea '{task['texto']}' marcada como notificada.")
                except ValueError as ve:
                    print(f"[WARNING] Error en formato de fecha/hora de tarea {task.get('id', 'N/A')}: {ve} (Valor problematico: '{task_datetime_str}')")
                except Exception as e:
                    print(f"[ERROR] Error al procesar notificación para tarea {task.get('id', 'N/A')}: {e}")
                    traceback.print_exc()

        except Exception as e:
            print(f"[ERROR] Error al recuperar tareas para notificación: {e}")
            traceback.print_exc()

        # --- Notificaciones para Citas ---
        try:
            # DEBUG: Imprimir la consulta y los filtros antes de ejecutar
            print(f"[DEBUG_DB] Querying 'cita' with conditions: completada=False, notified=False (hora filter handled in Python)")
            citas_to_notify_response = supabase.from_('cita').select('id,nombre,fecha,hora') \
                                            .eq('completada', False) \
                                            .eq('notified', False) \
                                            .execute()
            
            citas_to_notify = citas_to_notify_response.data
            # DEBUG: Imprimir los datos recuperados
            print(f"[DEBUG_DB] Raw citas retrieved: {citas_to_notify}")

            for cita in citas_to_notify:
                # IMPORTANT: Handle None or "None" string values for 'hora' explicitly in Python
                if not cita['hora'] or str(cita['hora']).lower() == 'none':
                    print(f"[DEBUG_CITA] Skipping cita {cita['id']} due to invalid or missing hora: '{cita['hora']}'")
                    continue

                # DEBUG: Imprimir los datos de la cita antes de la conversión de fecha/hora
                print(f"[DEBUG_CITA] Processing cita: ID={cita['id']}, Fecha={cita['fecha']}, Hora={cita['hora']}")
                cita_datetime_str = f"{cita['fecha']} {cita['hora']}"
                try:
                    # UPDATED: Changed from '%H:%M' to '%H:%M:%S' to correctly parse time with seconds
                    cita_full_datetime = datetime.strptime(cita_datetime_str, '%Y-%m-%d %H:%M:%S')
                    notify_time = cita_full_datetime - timedelta(minutes=15) # Notificar 15 minutos antes

                    print(f"[DEBUG_TIME] Cita '{cita['nombre']}' (ID: {cita['id']}) - Cita time: {cita_full_datetime}, Notify time: {notify_time}")

                    if notification_window_start <= notify_time <= notification_window_end:
                        print(f"[INFO] Preparando notificación para cita: {cita['nombre']} a las {cita['hora']} del {cita['fecha']}")
                        title = "Recordatorio de Cita"
                        body = f"¡Faltan 15 minutos para tu cita: {cita['nombre']} a las {cita['hora']}!"
                        
                        successful, failed, invalid = _send_push_notification_to_all(title, body)
                        print(f"[INFO] Notificación enviada para cita '{cita['nombre']}'. Éxito: {successful}, Fallo: {failed}")

                        if successful > 0: 
                            supabase.from_('cita').update({'notified': True}).eq('id', cita['id']).execute()
                            print(f"[INFO] Cita '{cita['nombre']}' marcada como notificada.")
                except ValueError as ve:
                    print(f"[WARNING] Error en formato de fecha/hora de cita {cita.get('id', 'N/A')}: {ve} (Valor problematico: '{cita_datetime_str}')")
                except Exception as e:
                    print(f"[ERROR] Error al procesar notificación para cita {cita.get('id', 'N/A')}: {e}")
                    traceback.print_exc()

        except Exception as e:
            print(f"[ERROR] Error al recuperar citas para notificación: {e}")
            traceback.print_exc()

# Rutas de la aplicación
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calendario')
def calendario():
    return render_template('calendario.html')

@app.route('/registros_importantes')
def registros_importantes_page():
    return render_template('registros_importantes.html')

@app.route('/lista')
def lista_compra_page():
    return render_template('lista.html')

@app.route('/notas')
def notas_rapidas_page():
    return render_template('notas.html')

@app.route('/citas')
def citas_page():
    return render_template('citas.html')

@app.route('/documentacion')
def documentacion_page():
    return render_template('documentacion.html')

@app.route('/alimentacion')
def alimentacion_page():
    return render_template('alimentacion.html')

@app.route('/gimnasio')
def gimnasio_page():
    return render_template('gimnasio.html')

# --- API Routes for Authentication ---
@app.route('/api/login', methods=['POST'])
def login():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    pin = data.get('pin')
    if pin == '1234':
        return jsonify({'message': 'Inicio de sesión exitoso'}), 200
    else:
        return jsonify({'error': 'PIN incorrecto'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    return jsonify({'message': 'Sesión cerrada'}), 200

# --- API Routes for Tasks ---
@app.route('/api/tareas/<string:fecha>', methods=['GET'])
def get_tareas_by_date(fecha):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido. Usar (YYYY-MM-DD)'}), 400

    try:
        response = supabase.from_('tarea').select('id,fecha,texto,completada,hora,notified').eq('fecha', fecha).order('hora').order('texto').execute()
        tareas = response.data
        return jsonify([
            {
                'id': tarea['id'],
                'fecha': tarea['fecha'],
                'texto': tarea['texto'],
                'completada': tarea['completada'],
                'hora': tarea['hora'],
                'notified': tarea.get('notified', False) 
            } for tarea in tareas
        ])
    except Exception as e:
        print(f"Error al obtener tareas por fecha de Supabase: {e}")
        return jsonify({'error': f'Error al obtener tareas: {str(e)}'}), 500

@app.route('/api/tareas/dias_con_tareas/<int:year>/<int:month>', methods=['GET'])
def get_dias_con_tareas(year, month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503

    start_date = date(year, month, 1)
    end_date = date(year, month, calendar.monthrange(year, month)[1])

    try:
        response = supabase.from_('tarea').select('fecha') \
                                        .gte('fecha', str(start_date)) \
                                        .lte('fecha', str(end_date)) \
                                        .execute()

        fechas = sorted(list(set([row['fecha'] for row in response.data])))
        return jsonify(fechas)
    except Exception as e:
        print(f"Error al obtener días con tareas de Supabase: {e}")
        return jsonify({'error': f'Error al obtener días con tareas: {str(e)}'}), 500

@app.route('/api/tareas', methods=['POST'])
def add_tarea():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    fecha = data.get('fecha')
    texto = data.get('texto')
    hora = data.get('hora')

    if not fecha or not texto:
        return jsonify({'error': 'La fecha y el texto de la tarea son obligatorios.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
        if hora:
            datetime.strptime(hora, '%H:%M')
    except ValueError:
        return jsonify({'error': 'Formato de fecha u hora inválido. Usar (YYYY-MM-DD) y HH:MM'}), 400

    hora_para_db = hora if hora else None

    try:
        # Añadido 'notified': False por defecto al crear una tarea
        insert_data = {'fecha': fecha, 'texto': texto, 'hora': hora_para_db, 'completada': False, 'notified': False}
        response = supabase.from_('tarea').insert(insert_data).execute()
        new_tarea = response.data[0]

        return jsonify({'id': new_tarea['id'], 'fecha': new_tarea['fecha'], 'texto': new_tarea['texto'], 'completada': new_tarea['completada'], 'hora': new_tarea['hora'], 'notified': new_tarea.get('notified')}), 201
    except Exception as e:
        print(f"Error al añadir tarea a Supabase: {e}")
        return jsonify({'error': f'Error al añadir tarea: {str(e)}'}), 500

@app.route('/api/tareas/<uuid:tarea_id>/toggle_completada', methods=['PATCH'])
def toggle_tarea_completada(tarea_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('tarea').select('completada').eq('id', str(tarea_id)).limit(1).execute()
        tarea = response.data[0] if response.data else None

        if not tarea:
            return jsonify({'error': 'Tarea no encontrada.'}), 404

        new_state = not tarea['completada']

        update_response = supabase.from_('tarea').update({'completada': new_state}).eq('id', str(tarea_id)).execute()

        if not update_response.data:
            return jsonify({'error': 'Tarea no encontrada o no se pudo actualizar.'}), 404

        return jsonify({'id': str(tarea_id), 'completada': new_state}), 200
    except Exception as e:
        print(f"Error al cambiar estado de tarea en Supabase: {e}")
        return jsonify({'error': f'Error al actualizar tarea: {str(e)}'}), 500

@app.route('/api/tareas/<uuid:tarea_id>', methods=['DELETE'])
def delete_tarea(tarea_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('tarea').delete().eq('id', str(tarea_id)).execute()

        if not delete_response.data:
            return jsonify({'error': 'Tarea no encontrada.'}), 404
        return jsonify({'message': 'Tarea eliminada exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar tarea de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar tarea: {str(e)}'}), 500

@app.route('/api/tareas/<uuid:task_id>/aplazar', methods=['PATCH'])
def aplazar_task(task_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    new_fecha = data.get('new_fecha')
    new_hora = data.get('new_hora')

    if not new_fecha:
        return jsonify({"error": "La nueva fecha es obligatoria para aplazar."}), 400

    try:
        datetime.strptime(new_fecha, '%Y-%m-%d')
        if new_hora:
            datetime.strptime(new_hora, '%H:%M')
    except ValueError:
        return jsonify({'error': 'Formato de fecha u hora inválido. Usar (YYYY-MM-DD) y HH:MM'}), 400

    new_hora_for_db = new_hora if new_hora else None

    try:
        # Al aplazar una tarea, la marcamos como no notificada de nuevo
        update_data = {'fecha': new_fecha, 'hora': new_hora_for_db, 'completada': False, 'notified': False}
        update_response = supabase.from_('tarea').update(update_data).eq('id', str(task_id)).execute()

        if not update_response.data:
            return jsonify({"error": "Tarea no encontrada para aplazar"}), 404
        return jsonify({"message": "Tarea aplazada exitosamente."}), 200
    except Exception as e:
        print(f"Error de base de datos al aplazar tarea en Supabase: {e}")
        return jsonify({'error': f'Error de base de datos: {str(e)}'}), 500

# --- API Routes for Important Records ---
@app.route('/api/registros_importantes/add_from_task', methods=['POST'])
def add_registro_from_task():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json

    fecha = data.get('fecha')
    titulo = data.get('titulo')
    descripcion = data.get('descripcion')
    tipo = data.get('tipo')
    imagen_base64 = data.get('imagen_base64')
    nombre_archivo = data.get('nombre_archivo')
    mime_type = data.get('mime_type')

    if not fecha or not titulo:
        return jsonify({'error': 'La fecha y el título son obligatorios para el registro importante.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except (ValueError, TypeError):
        return jsonify({'error': 'Formato de fecha inválido. Usar (YYYY-MM-DD)'}), 400

    try:
        insert_data = {
            'fecha': fecha,
            'titulo': titulo,
            'descripcion': descripcion,
            'tipo': tipo,
            'imagen_base64': imagen_base64,
            'nombre_archivo': nombre_archivo,
            'mime_type': mime_type
        }
        response = supabase.from_('registro_importante').insert(insert_data).execute()
        new_registro = response.data[0]

        return jsonify({'message': 'Registro importante guardado', 'id': new_registro['id']}), 201
    except Exception as e:
        print(f"Error al guardar registro importante en Supabase: {e}")
        return jsonify({'error': f'Error al guardar registro importante: {str(e)}'}), 500

@app.route('/api/registros_importantes', methods=['GET'])
def get_registros_importantes():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('registro_importante').select('id,fecha,titulo,descripcion,tipo,imagen_base64,nombre_archivo,mime_type').order('fecha', desc=True).order('id', desc=True).execute()
        registros = response.data
        return jsonify([
            {
                'id': registro['id'],
                'fecha': registro['fecha'],
                'titulo': registro['titulo'],
                'descripcion': registro['descripcion'],
                'tipo': registro['tipo'],
                'imagen_base64': registro.get('imagen_base64'),
                'nombre_archivo': registro.get('nombre_archivo'),
                'mime_type': registro.get('mime_type')
            } for registro in registros
        ])
    except Exception as e:
        print(f"Error al obtener registros importantes de Supabase: {e}")
        return jsonify({'error': f'Error al obtener registros importantes: {str(e)}'}), 500

@app.route('/api/registros_importantes/<uuid:registro_id>', methods=['GET'])
def get_registro_importante_by_id(registro_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('registro_importante').select('id,fecha,titulo,descripcion,tipo,imagen_base64,nombre_archivo,mime_type').eq('id', str(registro_id)).limit(1).execute()
        registro = response.data[0] if response.data else None
        if not registro:
            return jsonify({'error': 'Registro importante no encontrado.'}), 404
        return jsonify({
            'id': registro['id'],
            'nombre': registro['titulo'], 
            'fecha': registro['fecha'],
            'descripcion': registro['descripcion'],
            'tipo': registro['tipo'],
            'imagen_base64': registro.get('imagen_base64'),
            'nombre_archivo': registro.get('nombre_archivo'),
            'mime_type': registro.get('mime_type')
        }), 200
    except Exception as e:
        print(f"Error al obtener registro importante por ID de Supabase: {e}")
        return jsonify({'error': f'Error al obtener registro importante: {str(e)}'}), 500

@app.route('/api/registros_importantes/<uuid:registro_id>', methods=['PUT'])
def update_registro_importante(registro_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json

    fecha = data.get('fecha')
    titulo = data.get('titulo')
    descripcion = data.get('descripcion')
    tipo = data.get('tipo')
    imagen_base64 = data.get('imagen_base64')
    nombre_archivo = data.get('nombre_archivo')
    mime_type = data.get('mime_type')

    if not fecha or not titulo:
        return jsonify({'error': 'La fecha y el título son obligatorios para la actualización del registro importante.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except (ValueError, TypeError):
        return jsonify({'error': 'Formato de fecha inválido. Usar (YYYY-MM-DD)'}), 400

    try:
        update_data = {
            'fecha': fecha,
            'titulo': titulo,
            'descripcion': descripcion,
            'tipo': tipo,
            'imagen_base64': imagen_base64,
            'nombre_archivo': nombre_archivo,
            'mime_type': mime_type
        }
        response = supabase.from_('registro_importante').update(update_data).eq('id', str(registro_id)).execute()

        if not response.data:
            return jsonify({'error': 'Registro importante no encontrado para actualizar.'}), 404

        updated_registro = response.data[0]
        return jsonify({
            'message': 'Registro importante actualizado',
            'id': updated_registro['id'],
            'fecha': updated_registro['fecha'],
            'titulo': updated_registro['titulo'],
            'descripcion': updated_registro['descripcion'],
            'tipo': updated_registro['tipo'],
            'imagen_base64': updated_registro.get('imagen_base64'),
            'nombre_archivo': updated_registro.get('nombre_archivo'),
            'mime_type': updated_registro.get('mime_type')
        }), 200
    except Exception as e:
        print(f"Error al actualizar registro importante en Supabase: {e}")
        return jsonify({'error': f'Error al actualizar registro importante: {str(e)}'}), 500

@app.route('/api/registros_importantes/dias_con_registros/<int:year>/<int:month>', methods=['GET'])
def get_dias_con_registros(year, month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503

    start_date = date(year, month, 1)
    end_date = date(year, month, calendar.monthrange(year, month)[1])

    try:
        response = supabase.from_('registro_importante').select('fecha') \
                                                        .gte('fecha', str(start_date)) \
                                                        .lte('fecha', str(end_date)) \
                                                        .execute()
        fechas = sorted(list(set([row['fecha'] for row in response.data])))
        return jsonify(fechas)
    except Exception as e:
        print(f"Error al obtener días con registros de Supabase: {e}")
        return jsonify({'error': f'Error al obtener días con registros: {str(e)}'}), 500

@app.route('/api/registros_importantes/<uuid:registro_id>', methods=['DELETE'])
def delete_registro_importante(registro_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('registro_importante').delete().eq('id', str(registro_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Registro importante no encontrado.'}), 404
        return jsonify({'message': 'Registro importante eliminado exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar registro importante de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar registro importante: {str(e)}'}), 500

@app.route('/api/tipos_registro', methods=['GET'])
def get_tipos_registro():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('tipo_registro').select('id,nombre').order('nombre').execute()
        tipos = response.data
        return jsonify([
            {
                'id': tipo['id'],
                'nombre': tipo['nombre']
            } for tipo in tipos
        ])
    except Exception as e:
        print(f"Error al obtener tipos de registro de Supabase: {e}")
        return jsonify({'error': f'Error al obtener tipos de registro: {str(e)}'}), 500

# --- API Routes for Documentation ---
@app.route('/api/documentacion', methods=['POST'])
def add_documento():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json

    fecha = data.get('fecha')
    titulo = data.get('titulo')
    descripcion = data.get('descripcion')
    tipo = data.get('tipo')
    imagen_base64 = data.get('imagen_base64')
    nombre_archivo = data.get('nombre_archivo')
    mime_type = data.get('mime_type')

    if not fecha or not titulo:
        return jsonify({'error': 'La fecha y el título son obligatorios para el documento.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except (ValueError, TypeError):
        return jsonify({'error': 'Formato de fecha inválido. Usar (YYYY-MM-DD)'}), 400

    try:
        insert_data = {
            'fecha': fecha,
            'titulo': titulo,
            'descripcion': descripcion,
            'tipo': tipo,
            'imagen_base64': imagen_base64,
            'nombre_archivo': nombre_archivo,
            'mime_type': mime_type
        }
        response = supabase.from_('documentacion').insert(insert_data).execute()
        new_documento = response.data[0]

        return jsonify({'message': 'Documento guardado', 'id': new_documento['id']}), 201
    except Exception as e:
        print(f"Error al guardar documento en Supabase: {e}")
        return jsonify({'error': f'Error al guardar documento: {str(e)}'}), 500

@app.route('/api/documentacion', methods=['GET'])
def get_documentacion():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('documentacion').select('id,fecha,titulo,descripcion,tipo,imagen_base64,nombre_archivo,mime_type').order('fecha', desc=True).order('id', desc=True).execute()
        documentos = response.data
        return jsonify([
            {
                'id': doc['id'],
                'fecha': doc['fecha'],
                'titulo': doc['titulo'],
                'descripcion': doc['descripcion'],
                'tipo': doc['tipo'],
                'imagen_base64': doc.get('imagen_base64'),
                'nombre_archivo': doc.get('nombre_archivo'),
                'mime_type': doc.get('mime_type')
            } for doc in documentos
        ])
    except Exception as e:
        print(f"Error al obtener documentación de Supabase: {e}")
        return jsonify({'error': f'Error al obtener documentación: {str(e)}'}), 500

@app.route('/api/documentacion/dias_con_documentos/<int:year>/<int:month>', methods=['GET'])
def get_dias_con_documentos(year, month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503

    start_date = date(year, month, 1)
    end_date = date(year, month, calendar.monthrange(year, month)[1])

    try:
        response = supabase.from_('documentacion').select('fecha') \
                                                .gte('fecha', str(start_date)) \
                                                .lte('fecha', str(end_date)) \
                                                .execute()
        fechas = sorted(list(set([row['fecha'] for row in response.data])))
        return jsonify(fechas)
    except Exception as e:
        print(f"Error al obtener días con documentos de Supabase: {e}")
        return jsonify({'error': f'Error al obtener días con documentos: {str(e)}'}), 500

@app.route('/api/documentacion/<uuid:documento_id>', methods=['DELETE'])
def delete_documento(documento_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('documentacion').delete().eq('id', str(documento_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Documento no encontrado.'}), 404
        return jsonify({'message': 'Documento eliminado exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar documento de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar documento: {str(e)}'}), 500

@app.route('/api/tipos_documento', methods=['GET'])
def get_tipos_documento():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('tipo_documento').select('id,nombre').order('nombre').execute()
        tipos = response.data
        return jsonify([
            {
                'id': tipo['id'],
                'nombre': tipo['nombre']
            } for tipo in tipos
        ])
    except Exception as e:
        print(f"Error al obtener tipos de documento de Supabase: {e}")
        return jsonify({'error': f'Error al obtener tipos de documento: {str(e)}'}), 500

# --- API Routes for Routines ---
@app.route('/api/rutinas', methods=['POST'])
def add_rutina():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    nombre = data.get('nombre')
    hora = data.get('hora')
    hora_fin = data.get('hora_fin')
    dias = data.get('dias')

    if not nombre or not dias:
        return jsonify({'error': 'El nombre y los días de la semana de la rutina son obligatorios.'}), 400

    if not isinstance(dias, list) or not all(isinstance(d, int) and 0 <= d <= 6 for d in dias):
        return jsonify({'error': 'Los días deben ser una lista de enteros entre 0 y 6.'}), 400

    if hora:
        try:
            datetime.strptime(hora, '%H:%M')
        except ValueError:
            return jsonify({'error': 'Formato de hora inválido para la hora de inicio. Usar HH:MM'}), 400

    if hora_fin:
        try:
            datetime.strptime(hora_fin, '%H:%M')
        except ValueError:
            return jsonify({'error': 'Formato de hora inválido para la hora de fin. Usar HH:MM'}), 400

    hora_para_db = hora if hora else None
    hora_fin_para_db = hora_fin if hora_fin else None

    try:
        dias_semana_json = json.dumps(dias)
        insert_data = {'nombre': nombre, 'hora': hora_para_db, 'hora_fin': hora_fin_para_db, 'dias_semana': dias_semana_json}
        response = supabase.from_('rutina').insert(insert_data).execute()
        new_rutina = response.data[0]

        return jsonify({'id': new_rutina['id'], 'nombre': new_rutina['nombre'], 'hora': new_rutina['hora'], 'hora_fin': new_rutina.get('hora_fin'), 'dias': dias}), 201
    except Exception as e:
        print(f"Error al añadir rutina a Supabase: {e}")
        return jsonify({'error': f'Error al añadir rutina: {str(e)}'}), 500

@app.route('/api/rutinas', methods=['GET'])
def get_rutinas():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('rutina').select('id,nombre,hora,hora_fin,dias_semana').order('id', desc=True).execute()
        rutinas = response.data

        rutinas_list = []
        for rutina in rutinas:
            raw_dias_semana = rutina['dias_semana']
            dias_semana_list = []
            if raw_dias_semana:
                try:
                    dias_semana_list = json.loads(raw_dias_semana)
                    if not isinstance(dias_semana_list, list):
                        dias_semana_list = []
                except (json.JSONDecodeError, TypeError):
                    dias_semana_list = []
                    print(f"Advertencia: No se pudo decodificar dias_semana para la rutina {rutina['id']}. Valor: {raw_dias_semana}")

            rutinas_list.append({
                'id': rutina['id'],
                'nombre': rutina['nombre'],
                'hora': rutina['hora'],
                'hora_fin': rutina.get('hora_fin'),
                'dias': dias_semana_list
            })
        return jsonify(rutinas_list), 200
    except Exception as e:
        print(f"Error al obtener rutinas de Supabase: {e}")
        return jsonify({'error': f'Error al obtener rutinas: {str(e)}'}), 500

@app.route('/api/rutinas/completadas_por_dia/<string:fecha>', methods=['GET'])
def get_rutinas_completadas_por_dia(fecha):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('rutina_completada_dia').select('rutina_id').eq('fecha_completado', fecha).execute()
        completed_routine_ids = [item['rutina_id'] for item in response.data]
        return jsonify(completed_routine_ids), 200
    except Exception as e:
        print(f"Error al obtener rutinas completadas por día: {e}")
        return jsonify({'error': f'Error al obtener rutinas completadas: {str(e)}'}), 500

@app.route('/api/rutinas/<uuid:rutina_id>/toggle_completada_dia', methods=['POST'])
def toggle_rutina_completada_dia(rutina_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    fecha = data.get('fecha')

    if not fecha:
        return jsonify({'error': 'La fecha es obligatoria para actualizar el estado de la rutina.'}), 400

    try:
        response = supabase.from_('rutina_completada_dia').select('id').eq('rutina_id', str(rutina_id)).eq('fecha_completado', fecha).execute()

        if response.data:
            delete_response = supabase.from_('rutina_completada_dia').delete().eq('rutina_id', str(rutina_id)).eq('fecha_completado', fecha).execute()
            if not delete_response.data:
                raise Exception("No se pudo desmarcar la rutina como completada.")
            return jsonify({'message': 'Rutina marcada como incompleta para el día.'}), 200
        else:
            insert_data = {'rutina_id': str(rutina_id), 'fecha_completado': fecha}
            insert_response = supabase.from_('rutina_completada_dia').insert(insert_data).execute()
            if not insert_response.data:
                raise Exception("No se pudo marcar la rutina como completada.")
            return jsonify({'message': 'Rutina marcada como completada para el día.'}), 201
    except Exception as e:
        print(f"Error al cambiar el estado de la rutina por día: {e}")
        return jsonify({'error': f'Error al actualizar el estado de la rutina: {str(e)}'}), 500

# --- API Routes for Lists ---
@app.route('/api/lista_compra', methods=['GET'])
def get_lista_compra():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('lista_compra').select('id, item, comprada, ingredient_id').order('id', desc=True).execute()
        items = response.data

        processed_items = []
        for item in items:
            ingredient_name = None
            price_per_unit = 0.0
            cantidad_estandar = None
            unidad_medida = None

            if item['ingredient_id']:
                ingredient_response = supabase.from_('ingredients').select('name').eq('id', item['ingredient_id']).single().execute()
                ingredient_data = ingredient_response.data

                if ingredient_data:
                    ingredient_name = ingredient_data['name']
                    prices_response = supabase.from_('ingredient_prices').select('price, calories_per_100g, proteins_per_100g, cantidad_estandar, unidad_medida').eq('ingredient_id', item['ingredient_id']).order('price').limit(1).execute()
                    if prices_response.data:
                        price_per_unit = prices_response.data[0]['price']
                        cantidad_estandar = prices_response.data[0].get('cantidad_estandar')
                        unidad_medida = prices_response.data[0].get('unidad_medida')

            processed_items.append({
                'id': item['id'],
                'item': item['item'],
                'comprada': item['comprada'],
                'ingredient_id': item['ingredient_id'],
                'ingredient_name': ingredient_name,
                'price_per_unit': price_per_unit,
                'cantidad_estandar': cantidad_estandar,
                'unidad_medida': unidad_medida
            })
        return jsonify(processed_items), 200
    except Exception as e:
        print(f"Error al obtener la lista de la compra de Supabase: {e}")
        return jsonify({'error': f'Error al obtener la lista de la compra: {str(e)}'}), 500

@app.route('/api/lista_compra', methods=['POST'])
def add_item_lista_compra():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    item_text = data.get('item')
    ingredient_id = data.get('ingredient_id')

    if not item_text:
        return jsonify({'error': 'El texto del ítem es obligatorio.'}), 400

    try:
        insert_data = {'item': item_text, 'comprada': False, 'ingredient_id': ingredient_id}
        response = supabase.from_('lista_compra').insert(insert_data).execute()
        new_item = response.data[0]

        return jsonify({'id': new_item['id'], 'item': new_item['item'], 'comprada': new_item['comprada'], 'ingredient_id': new_item['ingredient_id']}), 201
    except Exception as e:
        print(f"Error al añadir ítem a la lista de la compra en Supabase: {e}")
        return jsonify({'error': f'Error al añadir ítem: {str(e)}'}), 500

@app.route('/api/lista_compra/<uuid:item_id>/toggle_comprada', methods=['PATCH'])
def toggle_item_comprada(item_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('lista_compra').select('comprada').eq('id', str(item_id)).limit(1).execute()
        item = response.data[0] if response.data else None

        if not item:
            return jsonify({'error': 'Ítem no encontrado.'}), 404

        new_state = not item['comprada']
        update_response = supabase.from_('lista_compra').update({'comprada': new_state}).eq('id', str(item_id)).execute()

        if not update_response.data:
            return jsonify({'error': 'Ítem no encontrado o no se pudo actualizar.'}), 404

        return jsonify({'id': str(item_id), 'comprada': new_state}), 200
    except Exception as e:
        print(f"Error al cambiar el estado del ítem en Supabase: {e}")
        return jsonify({'error': f'Error al cambiar el estado del ítem: {str(e)}'}), 500

@app.route('/api/lista_compra/<uuid:item_id>', methods=['PATCH'])
def update_lista_compra_item(item_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json

    update_data = {}
    if 'ingredient_id' in data:
        update_data['ingredient_id'] = data['ingredient_id']
    if 'item' in data:
        update_data['item'] = data['item']
    if 'comprada' in data:
        update_data['comprada'] = data['comprada']

    if not update_data:
        return jsonify({'error': 'No se proporcionaron datos para la actualización.'}), 400

    try:
        update_response = supabase.from_('lista_compra').update(update_data).eq('id', str(item_id)).execute()

        if not update_response.data:
            return jsonify({'error': 'Ítem no encontrado o no se pudo actualizar.'}), 404
        return jsonify({'message': 'Ítem actualizado exitosamente.', 'id': str(item_id)}), 200
    except Exception as e:
        print(f"Error al actualizar el ítem de la lista de la compra en Supabase: {e}")
        return jsonify({'error': f'Error al actualizar el ítem: {str(e)}'}), 500

@app.route('/api/lista_compra/<uuid:item_id>', methods=['DELETE'])
def delete_item_lista_compra(item_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('lista_compra').delete().eq('id', str(item_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Ítem no encontrado.'}), 404
        return jsonify({'message': 'Ítem eliminado exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar ítem de la lista de la compra de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar ítem: {str(e)}'}), 500

@app.route('/api/lista_compra/clear_all', methods=['DELETE'])
def clear_all_shopping_list_items():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('lista_compra').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()

        if delete_response.data is None:
             return jsonify({'message': 'Lista de la compra borrada exitosamente.'}), 200
        else:
             return jsonify({'message': 'Lista de la compra borrada exitosamente.', 'details': delete_response.data}), 200

    except Exception as e:
        print(f"Error de base de datos al limpiar todos los ítems de la lista de la compra en Supabase: {e.args[0]}")
        return jsonify({'error': f"Error de base de datos: {e.args[0]}"}), 500

# --- NEW API Routes for Quick Notes ---
@app.route('/api/notas', methods=['POST'])
def add_nota_rapida():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    texto = data.get('texto')
    fecha = data.get('fecha')

    if not texto:
        return jsonify({'error': 'El texto de la nota es obligatorio.'}), 400

    if not fecha:
        fecha = datetime.now().strftime('%Y-%m-%d')

    try:
        insert_data = {'texto': texto, 'fecha': fecha}
        response = supabase.from_('nota_rapida').insert(insert_data).execute()
        new_note = response.data[0]
        return jsonify({'id': new_note['id'], 'texto': new_note['texto'], 'fecha': new_note['fecha']}), 201
    except Exception as e:
        print(f"Error al añadir nota rápida a Supabase: {e}")
        return jsonify({'error': f'Error al añadir nota: {str(e)}'}), 500

@app.route('/api/notas', methods=['GET'])
def get_notas_rapidas():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('nota_rapida').select('id,texto,fecha').order('fecha', desc=True).order('id', desc=True).execute()
        notas = response.data
        return jsonify([
            {
                'id': nota['id'],
                'texto': nota['texto'],
                'fecha': nota['fecha']
            } for nota in notas
        ])
    except Exception as e:
        print(f"Error al obtener notas rápidas de Supabase: {e}")
        return jsonify({'error': f'Error al obtener notas: {str(e)}'}), 500

@app.route('/api/notas/<uuid:note_id>', methods=['DELETE'])
def delete_nota_rapida(note_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('nota_rapida').delete().eq('id', str(note_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Nota no encontrada.'}), 404
        return jsonify({'message': 'Nota eliminada exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar nota rápida de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar nota: {str(e)}'}), 500

# --- NEW API Routes for Citas ---
@app.route('/api/citas', methods=['POST'])
def add_cita():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    nombre = data.get('nombre')
    fecha = data.get('fecha')
    hora = data.get('hora')
    recordatorio = data.get('recordatorio')

    if not nombre or not fecha:
        return jsonify({'error': 'El nombre y la fecha de la cita son obligatorios.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
        if hora:
            datetime.strptime(hora, '%H:%M')
    except ValueError:
        return jsonify({'error': 'Formato de fecha u hora inválido. Usar (YYYY-MM-DD) y HH:MM'}), 400

    hora_para_db = hora if hora else None

    try:
        # Añadido 'notified': False por defecto al crear una cita
        insert_data = {'nombre': nombre, 'fecha': fecha, 'hora': hora_para_db, 'completada': False, 'recordatorio': recordatorio, 'notified': False}
        response = supabase.from_('cita').insert(insert_data).execute()
        new_cita = response.data[0]
        return jsonify({'id': new_cita['id'], 'nombre': new_cita['nombre'], 'fecha': new_cita['fecha'], 'hora': new_cita['hora'], 'completada': new_cita['completada'], 'recordatorio': new_cita.get('recordatorio'), 'notified': new_cita.get('notified')}), 201
    except Exception as e:
        print(f"Error al añadir cita a Supabase: {e}")
        return jsonify({'error': f'Error al añadir cita: {str(e)}'}), 500

@app.route('/api/citas/all', methods=['GET'])
def get_all_citas():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada,recordatorio,notified').order('fecha').order('hora').execute()
        citas = response.data
        return jsonify([
            {
                'id': cita['id'],
                'nombre': cita['nombre'],
                'fecha': cita['fecha'],
                'hora': cita['hora'],
                'completada': cita['completada'],
                'recordatorio': cita.get('recordatorio'),
                'notified': cita.get('notified', False) 
            } for cita in citas
        ])
    except Exception as e:
        print(f"Error al obtener todas las citas de Supabase: {e}")
        return jsonify({'error': f'Error al obtener citas: {str(e)}'}), 500

@app.route('/api/citas/<string:fecha>', methods=['GET'])
def get_citas_by_date(fecha):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido. Usar (YYYY-MM-DD)'}), 400

    try:
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada,recordatorio,notified').eq('fecha', fecha).order('hora').execute()
        citas = response.data
        return jsonify([
            {
                'id': cita['id'],
                'nombre': cita['nombre'],
                'fecha': cita['fecha'],
                'hora': cita['hora'],
                'completada': cita['completada'],
                'recordatorio': cita.get('recordatorio'),
                'notified': cita.get('notified', False) 
            } for cita in citas
        ])
    except Exception as e:
        print(f"Error al obtener citas por fecha de Supabase: {e}")
        return jsonify({'error': f'Error al obtener citas por fecha: {str(e)}'}), 500

@app.route('/api/citas/<int:year>/<int:month>', methods=['GET'])
def get_citas_for_month(year, month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503

    today = datetime.now().date()
    start_date = date(year, month, 1)
    end_date = date(year, month, calendar.monthrange(year, month)[1])

    try:
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada,recordatorio,notified').gte('fecha', str(start_date)).lte('fecha', str(end_date)).order('fecha').order('hora').execute()
        citas = response.data

        processed_citas = []
        for cita in citas:
            cita_date = datetime.strptime(cita['fecha'], '%Y-%m-%d').date()
            diff_days = (cita_date - today).days

            processed_citas.append({
                'id': cita['id'],
                'nombre': cita['nombre'],
                'fecha': cita['fecha'],
                'hora': cita['hora'],
                'completada': cita['completada'],
                'dias_restantes': diff_days,
                'recordatorio': cita.get('recordatorio'),
                'notified': cita.get('notified', False) 
            })
        return jsonify(processed_citas)
    except Exception as e:
        print(f"Error al obtener citas para el mes de Supabase: {e}")
        return jsonify({'error': f'Error al obtener citas para el mes: {str(e)}'}), 500

@app.route('/api/citas/proximas/<int:year>/<int:month>', methods=['GET'])
def get_proximas_citas(year, month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503

    today = datetime.now().date()
    try:
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada,recordatorio,notified').gte('fecha', str(today)).order('fecha').order('hora').execute()
        citas = response.data

        processed_citas = []
        for cita in citas:
            cita_date = datetime.strptime(cita['fecha'], '%Y-%m-%d').date()
            diff_days = (cita_date - today).days

            processed_citas.append({
                'id': cita['id'],
                'nombre': cita['nombre'],
                'fecha': cita['fecha'],
                'hora': cita['hora'],
                'completada': cita['completada'],
                'dias_restantes': diff_days,
                'recordatorio': cita.get('recordatorio'),
                'notified': cita.get('notified', False) 
            })
        return jsonify(processed_citas)
    except Exception as e:
        print(f"Error al obtener próximas citas de Supabase: {e}")
        return jsonify({'error': f'Error al obtener próximas citas: {str(e)}'}), 500

@app.route('/api/citas/<uuid:cita_id>', methods=['GET'])
def get_cita_by_id(cita_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada,recordatorio,notified').eq('id', str(cita_id)).limit(1).execute()
        cita = response.data[0] if response.data else None
        if not cita:
            return jsonify({'error': 'Cita no encontrada.'}), 404
        return jsonify({
            'id': cita['id'],
            'nombre': cita['nombre'],
            'fecha': cita['fecha'],
            'hora': cita['hora'],
            'completada': cita['completada'],
            'recordatorio': cita.get('recordatorio'),
            'notified': cita.get('notified', False) 
        }), 200
    except Exception as e:
        print(f"Error al obtener cita por ID de Supabase: {e}")
        return jsonify({'error': f'Error al obtener cita: {str(e)}'}), 500

@app.route('/api/citas/<uuid:cita_id>', methods=['PUT'])
def update_cita(cita_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    nombre = data.get('nombre')
    fecha = data.get('fecha')
    hora = data.get('hora')
    recordatorio = data.get('recordatorio')

    if not nombre or not fecha:
        return jsonify({'error': 'El nombre y la fecha de la cita son obligatorios.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
        if hora:
            datetime.strptime(hora, '%H:%M')
    except ValueError:
        return jsonify({'error': 'Formato de fecha u hora inválido. Usar (YYYY-MM-DD) y HH:MM'}), 400

    hora_para_db = hora if hora else None

    try:
        # Al actualizar una cita, la marcamos como no notificada de nuevo
        update_data = {'nombre': nombre, 'fecha': fecha, 'hora': hora_para_db, 'recordatorio': recordatorio, 'notified': False}
        update_response = supabase.from_('cita').update(update_data).eq('id', str(cita_id)).execute()

        if not update_response.data:
            return jsonify({'error': 'Cita no encontrada para actualizar.'}), 404
        return jsonify({'message': 'Cita actualizada exitosamente.', 'id': str(cita_id)}), 200
    except Exception as e:
        print(f"Error al actualizar cita en Supabase: {e}")
        return jsonify({'error': f'Error al actualizar cita: {str(e)}'}), 500

@app.route('/api/citas/<uuid:cita_id>/toggle_completada', methods=['PATCH'])
def toggle_cita_completada(cita_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('cita').select('completada').eq('id', str(cita_id)).limit(1).execute()
        cita = response.data[0] if response.data else None

        if not cita:
            return jsonify({'error': 'Cita no encontrada.'}), 404

        new_state = not cita['completada']

        update_response = supabase.from_('cita').update({'completada': new_state}).eq('id', str(cita_id)).execute()

        if not update_response.data:
            return jsonify({'error': 'Cita no encontrada o no se pudo actualizar.'}), 404

        return jsonify({'id': str(cita_id), 'completada': new_state}), 200
    except Exception as e:
        print(f"Error al cambiar estado de cita en Supabase: {e}")
        return jsonify({'error': f'Error al actualizar cita: {str(e)}'}), 500

@app.route('/api/citas/<uuid:cita_id>/toggle_requisito_completado', methods=['PATCH'])
def toggle_requisito_completado(cita_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    requisito_index = data.get('index')

    if not isinstance(requisito_index, int):
        return jsonify({'error': 'El índice del requisito es obligatorio y debe ser un entero.'}), 400

    try:
        response = supabase.from_('cita').select('recordatorio').eq('id', str(cita_id)).limit(1).execute()
        cita = response.data[0]