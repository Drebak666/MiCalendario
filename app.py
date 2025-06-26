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
# Se han actualizado con las claves proporcionadas por el usuario.
# Si estas variables se establecen en el entorno (Render), tendrán prioridad.
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "4pq3PdWq8xkltisk7dfTAsGz7oPPN2DrW4B4BWZyeg")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "BGMP4VQwdgGJAvggtWzTikWRXOxuHPc8H3F7Daxtrqcp5geq8Pwj1jazJZbRUrJjp4t4bdiztoM1H5YLjTpVnG4")
# IMPORTANTE: Reemplaza "mailto:your_email@example.com" con un correo electrónico real
# Este correo se utiliza para identificar al remitente de las notificaciones en caso de abuso.
VAPID_CLAIMS = {"sub": "mailto:your_email@example.com"}

# INFO: Las claves VAPID ya no se intentan generar en el código, se leen desde variables de entorno.
# Se mostrará un error si no se pueden obtener, incluso con los valores por defecto.
if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
    print("[ERROR] Fallo crítico: Las variables de entorno VAPID_PRIVATE_KEY y VAPID_PUBLIC_KEY no están configuradas.")
    print("[ERROR] Por favor, genera estas claves y configúralas para habilitar las notificaciones push.")
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
                    # FIX: Changed from '%H:%M' to '%H:%M:%S' to correctly parse time WITH seconds
                    task_full_datetime = datetime.strptime(task_datetime_str, '%Y-%m-%d %H:%M:%S') 
                    notify_time = task_full_datetime - timedelta(minutes=15) # Notificar 15 minutos antes

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
                    # FIX: Changed from '%H:%M' to '%H:%M:%S' to correctly parse time WITH seconds
                    cita_full_datetime = datetime.strptime(cita_datetime_str, '%Y-%m-%d %H:%M:%S')
                    notify_time = cita_full_datetime - timedelta(minutes=15) # Notificar 15 minutos antes

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

        new_state = not item['completada']
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
        cita = response.data[0] if response.data else None

        if not cita:
            return jsonify({'error': 'Cita no encontrada.'}), 404

        current_recordatorio_json_str = cita.get('recordatorio')

        requisitos = []
        if current_recordatorio_json_str:
            try:
                requisitos = json.loads(current_recordatorio_json_str)
            except json.JSONDecodeError:
                print(f"Error al decodificar JSON del recordatorio para la cita {cita_id}: {current_recordatorio_json_str}")
                return jsonify({'error': 'Formato de recordatorio inválido.'}), 400 # Añadido el código de estado aquí

        if not (0 <= requisito_index < len(requisitos)):
            return jsonify({'error': 'Índice de requisito inválido.'}), 400

        requisitos[requisito_index]['checked'] = not requisitos[requisito_index]['checked']

        updated_recordatorio_json_str = json.dumps(requisitos)

        update_response = supabase.from_('cita').update({'recordatorio': updated_recordatorio_json_str}).eq('id', str(cita_id)).execute()

        if not update_response.data:
            return jsonify({'error': 'Cita no encontrada o no se pudo actualizar el requisito.'}), 404

        return jsonify({'message': 'Estado del requisito actualizado exitosamente.', 'id': str(cita_id), 'index': requisito_index, 'new_state': requisitos[requisito_index]['checked']}), 200
    except Exception as e:
        print(f"Error al alternar el estado del requisito en Supabase: {e}")
        return jsonify({'error': f'Error al actualizar requisito: {str(e)}'}), 500

@app.route('/api/citas/<uuid:cita_id>', methods=['DELETE'])
def delete_cita(cita_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('cita').delete().eq('id', str(cita_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Cita no encontrada.'}), 404
        return jsonify({'message': 'Cita eliminada exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar cita de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar cita: {str(e)}'}), 500

# --- API para Supermercados ---
@app.route('/api/supermarkets', methods=['POST'])
def add_supermarket():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    name = data.get('name')

    if not name:
        return jsonify({'error': 'El nombre del supermercado es obligatorio.'}), 400

    try:
        response = supabase.from_('supermarkets').insert({"name": name}).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        if "duplicate key value violates unique constraint" in str(e):
            return jsonify({'error': 'Ya existe un supermercado con ese nombre.'}), 409
        print(f"Error al añadir supermercado a Supabase: {e}")
        return jsonify({'error': f'Error al añadir supermercado: {str(e)}'}), 500

@app.route('/api/supermarkets', methods=['GET'])
def get_supermarkets():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('supermarkets').select("*").order('name').execute()
        return jsonify(response.data), 200
    except Exception as e:
        print(f"Error al obtener supermercados de Supabase: {e}")
        return jsonify({'error': f'Error al obtener supermercados: {str(e)}'}), 500

@app.route('/api/supermarkets/<uuid:supermarket_id>', methods=['DELETE'])
def delete_supermarket(supermarket_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('supermarkets').delete().eq('id', str(supermarket_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Supermercado no encontrado.'}), 404
        return jsonify({'message': 'Supermercado eliminado exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar supermercado de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar supermercado: {str(e)}'}), 500

# --- API para Ingredientes (Modificado para usar la tabla ingredient_prices) ---
@app.route('/api/ingredients', methods=['GET'])
def get_ingredients():
    if supabase is None:
        print("[ERROR] Supabase no está inicializado en get_ingredients.")
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        ingredients_response = supabase.from_('ingredients').select('*').order('name').execute()
        ingredients_data = ingredients_response.data
        print(f"[{datetime.now()}] Fetched {len(ingredients_data)} ingredients from Supabase.")

        ingredients_with_prices = []
        for ingredient in ingredients_data:
            ingredient_id_str = None
            try:
                if 'id' not in ingredient or ingredient['id'] is None:
                    print(f"Error: El ingrediente no tiene 'id': {ingredient}")
                    continue

                ingredient_id_str = str(ingredient['id'])

                prices_data = []
                try:
                    prices_response = supabase.from_('ingredient_prices').select('supermarket_id, price, calories_per_100g, proteins_per_100g, cantidad_estandar, unidad_medida').eq('ingredient_id', ingredient_id_str).execute()
                    prices_data = prices_response.data if prices_response.data is not None else []
                except Exception as price_e:
                    print(f"Error al obtener precios para el ingrediente {ingredient_id_str}: {price_e}")
                    traceback.print_exc()
                    prices_data = []

                ingredient_copy = ingredient.copy()
                ingredient_copy['prices'] = prices_data
                ingredients_with_prices.append(ingredient_copy)

            except Exception as inner_e:
                print(f"Error al procesar ingrediente {ingredient.get('id', 'N/A')}: {inner_e}")
                traceback.print_exc()
                continue

        print(f"[{datetime.now()}] Ingredientes procesados exitosamente. Retornando {len(ingredients_with_prices)} ingredientes con precios.")
        return jsonify(ingredients_with_prices), 200
    except Exception as e:
        print(f"Error inesperado en get_ingredients (nivel superior): {e}")
        traceback.print_exc()
        return jsonify({'error': f'Error inesperado al obtener ingredientes: {str(e)}'}), 500

@app.route('/api/ingredients', methods=['POST'])
def add_ingredient():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    name = data.get('name')
    calories_per_100g = data.get('calories_per_100g')
    proteins_per_100g = data.get('proteins_per_100g')
    cantidad_estandar = data.get('cantidad_estandar')
    unidad_medida = data.get('unidad_medida')

    calories_per_100g = calories_per_100g if calories_per_100g is not None else 0.0
    proteins_per_100g = proteins_per_100g if proteins_per_100g is not None else 0.0
    cantidad_estandar = cantidad_estandar if cantidad_estandar is not None else 0.0
    unidad_medida = unidad_medida if unidad_medida is not None else 'g'

    if not name:
        return jsonify({'error': 'El nombre del ingrediente es obligatorio.'}), 400

    try:
        existing_ingredient_response = supabase.from_('ingredients').select('id, name').eq('name', name).limit(1).execute()
        if existing_ingredient_response.data:
            return jsonify({'message': 'El ingrediente ya existe.', 'id': existing_ingredient_response.data[0]['id'], 'existing': True}), 200

        insert_data = {
            'name': name,
            'calories_per_100g': calories_per_100g,
            'proteins_per_100g': proteins_per_100g,
            'cantidad_estandar': cantidad_estandar,
            'unidad_medida': unidad_medida
        }
        response = supabase.from_('ingredients').insert(insert_data).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        print(f"Error al añadir ingrediente a Supabase: {e}")
        return jsonify({'error': f'Error al añadir ingrediente: {str(e)}'}), 500

@app.route('/api/ingredients/<uuid:ingredient_id>', methods=['PUT', 'DELETE'])
def handle_ingredient(ingredient_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503

    try:
        if request.method == 'PUT':
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Datos de actualización requeridos.'}), 400

            update_data = {
                'name': data.get('name'),
                'calories_per_100g': float(data['calories_per_100g']) if data.get('calories_100g') is not None else None,
                'proteins_per_100g': float(data['proteins_per_100g']) if data.get('proteins_per_100g') is not None else None,
                'cantidad_estandar': float(data['cantidad_estandar']) if data.get('cantidad_estandar') is not None else None,
                'unidad_medida': data.get('unidad_medida') if data.get('unidad_medida') is not None else None
            }

            update_data_filtered = {k: v for k, v in update_data.items() if v is not None}

            update_response = supabase.from_('ingredients').update(update_data_filtered).eq('id', str(ingredient_id)).execute()

            if not update_response.data:
                return jsonify({'error': 'Ingrediente no encontrado o no se pudo actualizar.'}), 404

            return jsonify(update_response.data[0]), 200

        elif request.method == 'DELETE':
            supabase.from_('ingredient_prices').delete().eq('ingredient_id', str(ingredient_id)).execute()

            delete_response = supabase.from_('ingredients').delete().eq('id', str(ingredient_id)).execute()
            if not delete_response.data:
                return jsonify({'error': 'Ingrediente no encontrado.'}), 404
            return jsonify({'message': 'Ingrediente y sus precios eliminados exitosamente.'}), 200

    except Exception as e:
        print(f"Error en la operación del ingrediente ({request.method}): {e}")
        return jsonify({'error': f'Error en la operación del ingrediente: {str(e)}'}), 500

# --- Rutas para Precios de Ingredientes (ingredient_prices) ---
@app.route('/api/ingredients/<uuid:ingredient_id>/prices', methods=['POST'])
def add_ingredient_price(ingredient_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    supermarket_id = data.get('supermarket_id')
    price = data.get('price')
    calories_per_100g = data.get('calories_per_100g')
    proteins_per_100g = data.get('proteins_per_100g')
    cantidad_estandar = data.get('cantidad_estandar')
    unidad_medida = data.get('unidad_medida')

    calories_per_100g = calories_per_100g if calories_per_100g is not None else 0.0
    proteins_per_100g = proteins_per_100g if proteins_per_100g is not None else 0.0
    cantidad_estandar = cantidad_estandar if cantidad_estandar is not None else 0.0
    unidad_medida = unidad_medida if unidad_medida is not None else 'g'

    if not supermarket_id or price is None:
        return jsonify({'error': 'El ID del supermercado y el precio son obligatorios.'}), 400
    if not isinstance(price, (int, float)) or price < 0:
        return jsonify({'error': 'El precio debe ser un número válido y no negativo.'}), 400

    try:
        ingredient_check = supabase.from_('ingredients').select('id').eq('id', str(ingredient_id)).limit(1).execute()
        if not ingredient_check.data:
            return jsonify({'error': 'Ingrediente no encontrado.'}), 404

        supermarket_check = supabase.from_('supermarkets').select('id').eq('id', str(supermarket_id)).limit(1).execute()
        if not supermarket_check.data:
            return jsonify({'error': 'Supermercado no encontrado.'}), 404

        insert_data = {
            'ingredient_id': str(ingredient_id),
            'supermarket_id': str(supermarket_id),
            'price': price,
            'calories_per_100g': calories_per_100g,
            'proteins_per_100g': proteins_per_100g,
            'cantidad_estandar': cantidad_estandar,
            'unidad_medida': unidad_medida
        }
        response = supabase.from_('ingredient_prices').insert(insert_data).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        if "duplicate key value violates unique constraint" in str(e):
            return jsonify({'error': 'Ya existe un precio para este ingrediente en este supermercado.'}), 409
        print(f"Error al añadir precio de ingrediente a Supabase: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Error al añadir precio de ingrediente: {str(e)}'}), 500

@app.route('/api/ingredients/<uuid:ingredient_id>/prices/<uuid:supermarket_id>', methods=['DELETE'])
def delete_ingredient_price(ingredient_id, supermarket_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('ingredient_prices').delete().eq('ingredient_id', str(ingredient_id)).eq('supermarket_id', str(supermarket_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Precio de ingrediente no encontrado para este supermercado.'}), 404
        return jsonify({'message': 'Precio de ingrediente eliminado exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar precio de ingrediente de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar precio de ingrediente: {str(e)}'}), 500

# API para Recetas
@app.route('/api/recipes', methods=['POST'])
def add_recipe():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    name = data.get('name')
    description = data.get('description')
    ingredients = data.get('ingredients')
    total_cost = data.get('total_cost')
    total_calories = data.get('calories_total')
    total_proteins = data.get('proteins_total')
    total_carbs = data.get('total_carbs', 0.0)
    total_fats = data.get('total_fats', 0.0)

    if not name or not ingredients:
        return jsonify({'error': 'El nombre y los ingredientes de la receta son obligatorios.'}), 400

    ingredients_json_str = json.dumps(ingredients)

    try:
        insert_data = {
            'name': name,
            'description': description,
            'ingredients': ingredients_json_str,
            'total_cost': total_cost if total_cost is not None else 0.0,
            'total_calories': total_calories if total_calories is not None else 0.0,
            'total_proteins': total_proteins if total_proteins is not None else 0.0,
            'total_carbs': total_carbs,
            'total_fats': total_fats
        }
        response = supabase.from_('recipes').insert(insert_data).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        print(f"Error al añadir receta a Supabase: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Error al añadir receta: {str(e)}'}), 500

@app.route('/api/recipes', methods=['GET'])
def get_recipes():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('recipes').select('*').order('name').execute()

        recipes_list = []
        for recipe in response.data:
            recipe_copy = recipe.copy()
            if isinstance(recipe_copy.get('ingredients'), str):
                try:
                    recipe_copy['ingredients'] = json.loads(recipe_copy['ingredients'])
                except json.JSONDecodeError:
                    print(f"Error al decodificar JSON de ingredientes para la receta {recipe_copy.get('id')}: {recipe_copy.get('ingredients')}. Se establecerá una lista vacía por defecto.")
                    recipe_copy['ingredients'] = []
            else:
                recipe_copy['ingredients'] = recipe_copy.get('ingredients', []) if recipe_copy.get('ingredients') is not None else []

            recipes_list.append(recipe_copy)

        return jsonify(recipes_list), 200
    except Exception as e:
        print(f"Error al obtener recetas de Supabase: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Error al obtener recetas: {str(e)}'}), 500

@app.route('/api/recipes/<uuid:recipe_id>', methods=['DELETE'])
def delete_recipe(recipe_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('recipes').delete().eq('id', str(recipe_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Receta no encontrada.'}), 404
        return jsonify({'message': 'Receta eliminada exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar receta de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar receta: {str(e)}'}), 500

@app.route('/api/recipes/<uuid:recipe_id>', methods=['PUT'])
def update_recipe(recipe_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()

    update_data = {
        'name': data.get('name'),
        'description': data.get('description'),
        'total_cost': float(data['total_cost']) if data.get('total_cost') is not None else None,
        'total_calories': float(data['calories_total']) if data.get('calories_total') is not None else None,
        'total_proteins': float(data['proteins_total']) if data.get('proteins_total') is not None else None,
        'total_carbs': float(data.get('total_carbs', 0.0)) if data.get('total_carbs') is not None else None,
        'total_fats': float(data.get('total_fats', 0.0)) if data.get('total_fats') is not None else None
    }

    ingredients = data.get('ingredients')
    if ingredients is not None:
        update_data['ingredients'] = json.dumps(ingredients)

    update_data_filtered = {k: v for k, v in update_data.items() if v is not None}

    if not update_data_filtered:
        return jsonify({'error': 'No se proporcionaron datos para la actualización.'}), 400

    try:
        response = supabase.from_('recipes').update(update_data_filtered).eq('id', str(recipe_id)).execute()
        if not response.data:
            return jsonify({'error': 'Receta no encontrada o no se pudo actualizar.'}), 404

        updated_recipe = response.data[0]
        if isinstance(updated_recipe.get('ingredients'), str):
            try:
                updated_recipe['ingredients'] = json.loads(updated_recipe['ingredients'])
            except json.JSONDecodeError:
                print(f"Error al decodificar JSON de ingredientes después de la actualización para la receta {updated_recipe.get('id')}. Se establecerá una lista vacía por defecto.")
                updated_recipe['ingredients'] = []
        else:
            updated_recipe['ingredients'] = updated_recipe.get('ingredients', []) if updated_recipe.get('ingredients') is not None else []
        return jsonify(updated_recipe), 200
    except Exception as e:
        print(f"Error al actualizar receta en Supabase: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Error al actualizar receta: {str(e)}'}), 500

# API para Menú Semanal (Singleton)
@app.route('/api/weekly_menu', methods=['GET', 'POST', 'PUT'])
def handle_weekly_menu_save():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503

    if request.method == 'GET':
        try:
            response = supabase.from_('weekly_menu').select('*').limit(1).execute()
            menu_data = response.data[0] if response.data else None

            if menu_data and isinstance(menu_data.get('menu'), str):
                try:
                    menu_data['menu'] = json.loads(menu_data['menu'])
                except json.JSONDecodeError:
                    print(f"Error al decodificar JSON del menú para el menú semanal {menu_data.get('id')}. Se establecerá un diccionario vacío por defecto.")
                    menu_data['menu'] = {}
            elif menu_data and menu_data.get('menu') is None:
                menu_data['menu'] = {}

            return jsonify(menu_data), 200
        except Exception as e:
            print(f"Error al obtener el menú semanal de Supabase: {e}")
            traceback.print_exc()
            return jsonify({'error': f'Error al obtener el menú semanal: {str(e)}'}), 500

    data = request.get_json()
    menu = data.get('menu')
    menu_id = data.get('id')

    if not menu:
        return jsonify({'error': 'Los datos del menú son obligatorios.'}), 400

    menu_json_str = json.dumps(menu)

    try:
        if request.method == 'PUT':
            if not menu_id:
                return jsonify({'error': 'ID del menú semanal es obligatorio para la actualización (PUT).'}), 400

            existing_menu_response = supabase.from_('weekly_menu').select('id').eq('id', str(menu_id)).limit(1).execute()
            if not existing_menu_response.data:
                return jsonify({'error': 'Menú semanal no encontrado para actualizar.'}), 404

            update_response = supabase.from_('weekly_menu').update({'menu': menu_json_str}).eq('id', str(menu_id)).execute()
            updated_menu = update_response.data[0]
            if isinstance(updated_menu.get('menu'), str):
                try:
                    updated_menu['menu'] = json.loads(updated_menu['menu'])
                except json.JSONDecodeError:
                    print(f"Error al decodificar JSON del menú después de la actualización para el menú semanal {updated_menu.get('id')}. Se establecerá un diccionario vacío por defecto.")
                    updated_menu['menu'] = {}
            else:
                updated_menu['menu'] = updated_menu.get('menu', {}) if updated_menu.get('menu') is not None else {}
            return jsonify(updated_menu), 200

        elif request.method == 'POST':
            existing_menu_response = supabase.from_('weekly_menu').select('id').limit(1).execute()
            if existing_menu_response.data:
                return jsonify({'error': 'Ya existe un menú semanal. Utiliza PUT para actualizarlo.'}), 409

            insert_response = supabase.from_('weekly_menu').insert({'menu': menu_json_str}).execute()
            new_menu = insert_response.data[0]
            if isinstance(new_menu.get('menu'), str):
                try:
                    new_menu['menu'] = json.loads(new_menu['menu'])
                except json.JSONDecodeError:
                    print(f"Error al decodificar JSON del menú después de la inserción para el menú semanal {new_menu.get('id')}. Se establecerá un diccionario vacío por defecto.")
                    new_menu['menu'] = {}
            else:
                new_menu['menu'] = new_menu.get('menu', {}) if new_menu.get('menu') is not None else {}
            return jsonify(new_menu), 201

    except Exception as e:
        print(f"Error al actualizar/añadir menú semanal en Supabase: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Error al actualizar/añadir menú semanal: {str(e)}'}), 500

# NEW: API for Gym Logs
@app.route('/api/gym_logs', methods=['POST'])
def add_gym_log():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    activity = data.get('activity')
    duration_minutes = data.get('duration_minutes')
    calories_burned = data.get('calories_burned')
    notes = data.get('notes')

    if not activity or duration_minutes is None:
        return jsonify({'error': 'La actividad y la duración son obligatorias.'}), 400

    try:
        insert_data = {
            'activity': activity,
            'duration_minutes': duration_minutes,
            'calories_burned': calories_burned,
            'notes': notes
        }
        response = supabase.from_('gym_logs').insert(insert_data).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        print(f"Error al añadir registro de gimnasio a Supabase: {e}")
        return jsonify({'error': f'Error al añadir registro de gimnasio: {str(e)}'}), 500

@app.route('/api/gym_logs', methods=['GET'])
def get_gym_logs():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('gym_logs').select('*').order('timestamp', desc=True).execute()
        logs = response.data
        return jsonify(logs), 200
    except Exception as e:
        print(f"Error al obtener registros de gimnasio de Supabase: {e}")
        return jsonify({'error': f'Error al obtener registros de gimnasio: {str(e)}'}), 500

@app.route('/api/gym_logs/<uuid:log_id>', methods=['DELETE'])
def delete_gym_log(log_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('gym_logs').delete().eq('id', str(log_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Registro de gimnasio no encontrado.'}), 404
        return jsonify({'message': 'Registro de gimnasio eliminado exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar registro de gimnasio de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar registro de gimnasio: {str(e)}'}), 500

# NEW: API to get VAPID public key for frontend
@app.route('/api/vapid_public_key', methods=['GET'])
def get_vapid_public_key():
    if not VAPID_PUBLIC_KEY:
        return jsonify({'error': 'VAPID public key not configured.'}), 500
    return jsonify({'publicKey': VAPID_PUBLIC_KEY}), 200

# NUEVO: Ruta para la página de notificaciones
@app.route('/notificaciones')
def notificaciones_page():
    return render_template('notificaciones.html')

# NUEVO: API para almacenar suscripciones push
@app.route('/api/subscribe', methods=['POST'])
def subscribe():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503

    data = request.json
    endpoint = data.get('endpoint')
    p256dh = data.get('keys', {}).get('p256dh')
    auth = data.get('keys', {}).get('auth')

    if not endpoint or not p256dh or not auth:
        return jsonify({'error': 'Datos de suscripción incompletos.'}), 400

    try:
        existing_subscription = supabase.from_('push_subscriptions').select('id').eq('endpoint', endpoint).limit(1).execute()
        if existing_subscription.data:
            print(f"[INFO] Suscripción existente detectada para endpoint: {endpoint}")
            return jsonify({'message': 'Suscripción ya existe y/o actualizada.'}), 200

        insert_data = {
            'endpoint': endpoint,
            'p256dh': p256dh,
            'auth': auth
        }
        response = supabase.from_('push_subscriptions').insert(insert_data).execute()
        return jsonify({'message': 'Suscripción guardada exitosamente.', 'id': response.data[0]['id']}), 201
    except Exception as e:
        print(f"Error al guardar la suscripción de push en Supabase: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Error al guardar suscripción: {str(e)}'}), 500

# NUEVO: API para enviar una notificación (para demostración/pruebas)
@app.route('/api/send_notification', methods=['POST'])
def send_notification():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503

    data = request.json
    title = data.get('title', 'Notificación de tu App')
    body = data.get('body', '¡Tienes una nueva notificación!')
    icon = data.get('icon', '/static/icons/notification-icon.png')

    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        return jsonify({'error': 'Claves VAPID no configuradas en el servidor.'}), 500

    successful_sends, failed_sends, invalid_subscriptions = _send_push_notification_to_all(title, body, icon)

    return jsonify({
        'message': f'Notificaciones enviadas. Éxito: {successful_sends}, Fallo: {failed_sends}',
        'invalid_subscriptions_removed': len(invalid_subscriptions)
    }), 200

# NUEVO: Ruta para el archivo Service Worker
@app.route('/service-worker.js')
def service_worker():
    # Asegúrate de que este archivo está en tu carpeta 'static'
    return send_from_directory(app.static_folder, 'service-worker.js', mimetype='application/javascript')

# Punto de entrada de la aplicación
if __name__ == '__main__':
    # Antes de ejecutar la app, inicializa la base de datos (tipos de registro/documento)
    init_db_supabase()
    
    # Inicia el scheduler
    # Evita que el scheduler se inicie dos veces si se usa Flask en modo debug con reloader
    if not scheduler.running: # Solo inicia el scheduler si no está ya en ejecución
        scheduler.init_app(app)
        scheduler.start()
        print("[INFO] APScheduler iniciado.")
    else:
        print("[INFO] APScheduler ya está en ejecución.")

    # Si quieres que las tareas de rutina se generen automáticamente al iniciar la aplicación (una vez al día).\
    # Descomenta la línea de abajo. Asegúrate de que el scheduler ya esté iniciado antes de llamar a esta función.\
    # generate_tasks_for_today_from_routines() # Considerar si esto es mejor como un job de APScheduler

    # Ejecuta la gestión de tareas atrasadas
    manage_overdue_tasks()

    port = int(os.environ.get("PORT", 5000))
    # Para desarrollo local, use_reloader=False evita que el scheduler se inicie dos veces
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False) 
