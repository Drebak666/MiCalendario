# En app.py
import os
import json
from datetime import datetime, date, timedelta
from supabase import create_client, Client
from flask import Flask, render_template, request, jsonify, g, session
from functools import wraps
import uuid # Import the uuid module
import calendar # Necessary for calendar.calendar.monthrange, although not explicitly in the user's provided version, I add it for consistency if any function needs it.
from flask_cors import CORS # IMPORTANTE: Importa Flask-CORS
import base64 # Import base64 at the top level for image handling
import traceback # Import traceback for detailed error logging

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secreto_y_cambiar_en_produccion") # Secret key for sessions
CORS(app) # IMPORTANTE: Habilita CORS para toda la aplicación Flask

# --- Supabase Configuration ---
# Es CRUCIAL usar variables de entorno para las credenciales en producción.
# Render te permite configurar estas variables en su Dashboard.
# Para desarrollo local, puedes configurarlas en tu entorno o usar un archivo .env.
# Manteniendo las claves hardcodeadas como en tu archivo original. Para producción, se recomiendan variables de entorno.
SUPABASE_URL = "https://ugpqqmcstqtywyrzfnjq.supabase.co" # EXAMPLE: "https://ugpqqmcstqtywyrzfnjq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVncHFxbWNzdHF0eXd5cnpmbmpxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk3Mzk2ODgsImV4cCI6MjA2NTMxNTY4OH0.nh56rQQliOnX5AZzePaZv_RB05uRIlUbfQPkWJPvKcE" # Asegúrate de que esta sea la clave completa y correcta de tu panel de Supabase.

supabase: Client = None

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[ERROR] Fallo crítico: Las variables de entorno SUPABASE_URL y SUPABASE_KEY no están configuradas.")
    print("[ERROR] Asegúrate de definirlas en tu entorno de despliegue (ej., Render) o localmente.")
else:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase conectado y cliente inicializado correctamente.")
    except Exception as e:
        print(f"[ERROR] Fallo crítico al conectar o inicializar Supabase: {e}")

# --- Simple Authentication Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': 'No autorizado. Se requiere autenticación.'}), 401
        return f(*args, **kwargs)
    return decorated_function

# --- Utility Functions (Adapted for Supabase) ---

def init_db_supabase():
    """
    Function to initialize the database in Supabase.
    Only inserts default data if necessary (for tipo_registro and tipo_documento).
    Tables must be created manually in the Supabase Dashboard.
    """
    if supabase is None:
        print("[WARNING] Supabase no está inicializado. No se pueden insertar tipos de registro/documento predeterminados.")
        return

    try:
        # Initialize tipo_registro
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
        # Initialize tipo_documento
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

# NUEVO: Tabla para almacenar la última fecha de generación de tareas
# Necesitarás crear una tabla en Supabase con una columna 'last_generation_date' (tipo: date)
# y, opcionalmente, un 'id' (UUID) y 'app_identifier' (texto) si quieres múltiples apps o una única entrada.
# Para este ejemplo, asumiremos una única entrada con un ID conocido o que la tabla solo tendrá una fila.
# Por ejemplo, puedes crear una tabla llamada `app_settings` con una columna `last_task_generation_date`.

def generate_tasks_for_today_from_routines():
    """
    Genera tareas para hoy a partir de las rutinas, adaptado para Supabase.
    Ahora incluye un mecanismo para asegurar que se ejecuta solo una vez al día.
    """
    if supabase is None:
        print("[WARNING] Supabase no está inicializado. No se pueden generar tareas a partir de rutinas.")
        return

    today_date_str = datetime.now().strftime('%Y-%m-%d')
    today_date_obj = datetime.now().date() # Obtener la fecha actual como objeto date
    today_day_of_week_py = datetime.now().weekday()
    # Mapear al formato HTML (0=Dom, 1=Lun, ..., 6=Sáb). Python weekday es 0=Lun, 6=Dom.
    today_day_of_week_html_format = (today_day_of_week_py + 1) % 7 # Lunes (0) -> 1, Domingo (6) -> 0

    print(f"[{datetime.now()}] Intentando generar tareas para hoy ({today_date_str}, día de la semana HTML: {today_day_of_week_html_format}) a partir de las rutinas.")

    try:
        # 1. Obtener la última fecha de generación
        # Asumiendo una tabla 'app_settings' con una columna 'last_task_generation_date'
        # Podrías usar un ID fijo para la única fila de configuración, por ejemplo, 'daily_tasks_setting_id'
        settings_response = supabase.from_('app_settings').select('last_task_generation_date').limit(1).execute()
        last_generation_date_str = settings_response.data[0]['last_task_generation_date'] if settings_response.data else None

        last_generation_date_obj = None
        if last_generation_date_str:
            try:
                last_generation_date_obj = datetime.strptime(last_generation_date_str, '%Y-%m-%d').date()
            except ValueError:
                print(f"[WARNING] Formato de fecha inválido en last_task_generation_date: {last_generation_date_str}. Se forzará la regeneración.")
                last_generation_date_obj = None # Forzar regeneración si el formato es malo

        # 2. Comprobar si ya se generaron tareas para hoy
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
                        'completada': False
                    }
                    insert_response = supabase.from_('tarea').insert(new_task_data).execute()
                    if insert_response.data:
                        print(f"[{datetime.now()}] Tarea '{routine_name}' generada para hoy a partir de la rutina {routine_id}. ID: {insert_response.data[0]['id']}.")
                    else:
                        print(f"[{datetime.now()}] Fallo al generar la tarea '{routine_name}' para hoy a partir de la rutina {routine_id}.")
        
        # 3. Actualizar la última fecha de generación después de la ejecución exitosa
        if settings_response.data:
            # Si ya existe una fila, actualiza
            supabase.from_('app_settings').update({'last_task_generation_date': today_date_str}).eq('id', settings_response.data[0]['id']).execute()
        else:
            # Si no existe, inserta una nueva fila (asumiendo que solo habrá una)
            # Podrías necesitar un ID fijo si no tienes un UUID autogenerado para esta tabla de configuración.
            # Aquí asumimos que Supabase autogenerará un UUID si 'id' no se especifica y la columna es de tipo UUID.
            supabase.from_('app_settings').insert({'last_task_generation_date': today_date_str}).execute()
        
        print(f"[{datetime.now()}] Generación de tareas a partir de rutinas finalizada y fecha de última generación actualizada a {today_date_str}.")

    except Exception as e:
        print(f"[ERROR] Error en generate_tasks_for_today_from_routines: {e}")
        # En caso de error, no actualizamos la fecha de última generación para reintentar en el siguiente inicio.


def manage_overdue_tasks():
    """
    Gestiona las tareas atrasadas, adaptado para Supabase.
    """
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

# --- Application Routes (No changes if they only render HTML) ---

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

@app.route('/alimentacion') # New route for the food page
def alimentacion_page():
    return render_template('alimentacion.html')

# NEW: Route for the gym page
@app.route('/gimnasio')
def gimnasio_page():
    return render_template('gimnasio.html')


# --- API Routes for Authentication ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    pin = data.get('pin')
    # WARNING: Hardcoded PIN for demonstration.
    # IN PRODUCTION, use a secure authentication system (e.g., Supabase Auth).
    if pin == '1234':
        session['logged_in'] = True
        return jsonify({'message': 'Inicio de sesión exitoso'}), 200
    else:
        return jsonify({'error': 'PIN incorrecto'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    return jsonify({'message': 'Sesión cerrada'}), 200


# --- API Routes for Tasks (Adapted for Supabase) ---

@app.route('/api/tareas/<string:fecha>', methods=['GET'])
def get_tareas_by_date(fecha):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido. Usar (YYYY-MM-DD)'}), 400

    try:
        response = supabase.from_('tarea').select('id,fecha,texto,completada,hora').eq('fecha', fecha).order('hora').order('texto').execute()
        tareas = response.data
        return jsonify([
            {
                'id': tarea['id'],
                'fecha': tarea['fecha'],
                'texto': tarea['texto'],
                'completada': tarea['completada'],
                'hora': tarea['hora']
            } for tarea in tareas
        ])
    except Exception as e:
        print(f"Error al obtener tareas por fecha de Supabase: {e}")
        return jsonify({'error': f'Error al obtener tareas: {str(e)}'}), 500

@app.route('/api/tareas/dias_con_tareas/<int:year>/<int:month>', methods=['GET'])
def get_dias_con_tareas(year, month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    
    # Construir el rango de fechas para el mes
    start_date = date(year, month, 1)
    # calendar.monthrange(year, month)[1] devuelve el número de días en el mes
    end_date = date(year, month, calendar.monthrange(year, month)[1])

    try:
        # Consulta para obtener fechas dentro del rango de mes
        # Esto es más robusto y usa comparaciones de fecha adecuadas
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
        insert_data = {'fecha': fecha, 'texto': texto, 'hora': hora_para_db, 'completada': False}
        response = supabase.from_('tarea').insert(insert_data).execute()
        new_tarea = response.data[0]

        return jsonify({'id': new_tarea['id'], 'fecha': new_tarea['fecha'], 'texto': new_tarea['texto'], 'completada': new_tarea['completada'], 'hora': new_tarea['hora']}), 201
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
        update_data = {'fecha': new_fecha, 'hora': new_hora_for_db, 'completada': False}
        update_response = supabase.from_('tarea').update(update_data).eq('id', str(task_id)).execute()
        
        if not update_response.data:
            return jsonify({"error": "Tarea no encontrada para aplazar"}), 404
        return jsonify({"message": "Tarea aplazada exitosamente."}), 200
    except Exception as e:
        print(f"Error de base de datos al aplazar tarea en Supabase: {e}")
        return jsonify({'error': f'Error de base de datos: {str(e)}'}), 500

# --- API Routes for Important Records (Adapted for Supabase) ---
# @login_required eliminado para hacerlos públicos, según la solicitud del usuario.
@app.route('/api/registros_importantes/add_from_task', methods=['POST'])
def add_registro_from_task():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json

    fecha = data.get('fecha')
    titulo = data.get('titulo')
    descripcion = data.get('descripcion')
    tipo = data.get('tipo') # Esto siempre será "General" en el nuevo frontend
    imagen_base64 = data.get('imagen_base64') # Contiene la imagen o archivo Base64
    nombre_archivo = data.get('nombre_archivo') # Nuevo: para guardar el nombre original del archivo
    mime_type = data.get('mime_type') # Nuevo: para guardar el tipo MIME del archivo

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
            'imagen_base64': imagen_base64, # Almacenar directamente la cadena base64
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
        # Añadir nuevas columnas a la selección
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

@app.route('/api/registros_importantes/dias_con_registros/<int:year>/<int:month>', methods=['GET'])
def get_dias_con_registros(year, month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    
    # Construir el rango de fechas para el mes
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
@login_required # Protegido (asumiendo que esto todavía requiere inicio de sesión, según el app.py original)
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
@login_required # Protegido
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
@login_required # Protegido
def get_dias_con_documentos(year, month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    
    # Construir el rango de fechas para el mes
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
@login_required # Protegido
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
@login_required # Protegido
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

# --- API Routes for Routines (Adapted for Supabase) ---

@app.route('/api/rutinas', methods=['POST'])
def add_rutina():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    nombre = data.get('nombre')
    hora = data.get('hora')
    hora_fin = data.get('hora_fin') # NUEVO: Obtener hora_fin
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
    
    if hora_fin: # NUEVO: Validar hora_fin
        try:
            datetime.strptime(hora_fin, '%H:%M')
        except ValueError:
            return jsonify({'error': 'Formato de hora inválido para la hora de fin. Usar HH:MM'}), 400
    
    hora_para_db = hora if hora else None
    hora_fin_para_db = hora_fin if hora_fin else None # NUEVO: Preparar hora_fin para la DB

    try:
        dias_semana_json = json.dumps(dias)
        # NUEVO: Incluir hora_fin en los datos a insertar
        insert_data = {'nombre': nombre, 'hora': hora_para_db, 'hora_fin': hora_fin_para_db, 'dias_semana': dias_semana_json}
        response = supabase.from_('rutina').insert(insert_data).execute()
        new_rutina = response.data[0]

        # NUEVO: Devolver hora_fin en la respuesta
        return jsonify({'id': new_rutina['id'], 'nombre': new_rutina['nombre'], 'hora': new_rutina['hora'], 'hora_fin': new_rutina.get('hora_fin'), 'dias': dias}), 201
    except Exception as e:
        print(f"Error al añadir rutina a Supabase: {e}")
        return jsonify({'error': f'Error al añadir rutina: {str(e)}'}), 500

@app.route('/api/rutinas', methods=['GET'])
def get_rutinas():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        # NUEVO: Seleccionar hora_fin también
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
                'hora_fin': rutina.get('hora_fin'), # NUEVO: Incluir hora_fin en la respuesta
                'dias': dias_semana_list
            })
        return jsonify(rutinas_list)
    except Exception as e:
        print(f"Error al obtener rutinas de Supabase: {e}")
        return jsonify({'error': f'Error al obtener rutinas: {str(e)}'}), 500

@app.route('/api/rutinas/<uuid:rutina_id>', methods=['DELETE'])
def delete_rutina(rutina_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('rutina').delete().eq('id', str(rutina_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Rutina no encontrada.'}), 404
        return jsonify({'message': 'Rutina eliminada exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar rutina de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar rutina: {str(e)}'}), 500

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


# --- API Routes for Lists (Adapted for Supabase) ---
@app.route('/api/lista_compra', methods=['GET'])
def get_lista_compra():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        # Incluir un join con ingredientes para obtener precio, nombre del ingrediente, cantidad_estandar y unidad_medida
        # NO se usa price_per_unit directamente del ingrediente, sino que se busca el precio más bajo en ingredient_prices
        response = supabase.from_('lista_compra').select('id, item, comprada, ingredient_id').order('id', desc=True).execute()
        items = response.data
        
        processed_items = []
        for item in items:
            ingredient_name = None
            price_per_unit = 0.0 # Precio por unidad del ingrediente
            cantidad_estandar = None # Initialize
            unidad_medida = None   # Initialize
            
            # Si el item está vinculado a un ingrediente, buscar sus detalles y precios
            if item['ingredient_id']:
                ingredient_response = supabase.from_('ingredients').select('name, cantidad_estandar, unidad_medida').eq('id', item['ingredient_id']).single().execute()
                ingredient_data = ingredient_response.data

                if ingredient_data:
                    ingredient_name = ingredient_data['name']
                    cantidad_estandar = ingredient_data.get('cantidad_estandar')
                    unidad_medida = ingredient_data.get('unidad_medida')

                    # Buscar el precio más bajo del ingrediente en cualquier supermercado
                    prices_response = supabase.from_('ingredient_prices').select('price').eq('ingredient_id', item['ingredient_id']).order('price').limit(1).execute()
                    if prices_response.data:
                        price_per_unit = prices_response.data[0]['price']

            processed_items.append({
                'id': item['id'],
                'item': item['item'],
                'comprada': item['comprada'],
                'ingredient_id': item['ingredient_id'],
                'ingredient_name': ingredient_name, # El nombre del ingrediente
                'price_per_unit': price_per_unit,  # El precio más bajo encontrado
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
    ingredient_id = data.get('ingredient_id') # Nuevo: ingredient_id opcional desde el frontend

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
        # CUIDADO: La columna en la DB es 'comprada', no 'completada'.
        response = supabase.from_('lista_compra').select('comprada').eq('id', str(item_id)).limit(1).execute()
        item = response.data[0] if response.data else None

        if not item:
            return jsonify({'error': 'Ítem no encontrado.'}), 404

        new_state = not item['comprada'] # Corregido de 'completada' a 'comprada'
        update_response = supabase.from_('lista_compra').update({'comprada': new_state}).eq('id', str(item_id)).execute() # Corregido de 'completada' a 'comprada'
        
        if not update_response.data:
            return jsonify({'error': 'Ítem no encontrado o no se pudo actualizar.'}), 404

        return jsonify({'id': str(item_id), 'comprada': new_state}), 200
    except Exception as e:
        print(f"Error al cambiar el estado del ítem en Supabase: {e}")
        return jsonify({'error': f'Error al cambiar el estado del ítem: {str(e)}'}), 500

# NUEVA RUTA: PATCH /api/lista_compra/<uuid:item_id> para actualizar cualquier campo, específicamente ingredient_id
@app.route('/api/lista_compra/<uuid:item_id>', methods=['PATCH'])
def update_lista_compra_item(item_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    
    # Permitir la actualización de campos específicos. Aquí, estamos principalmente interesados en 'ingredient_id'
    update_data = {}
    if 'ingredient_id' in data:
        update_data['ingredient_id'] = data['ingredient_id']
    if 'item' in data: # También permitir la actualización del texto del ítem si es necesario
        update_data['item'] = data['item']
    if 'comprada' in data: # Permitir la actualización del estado de compra
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
        # La forma de limpiar toda la tabla en Supabase sin WHERE
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
    # NUEVO: Obtener lista de requisitos (ya cadena JSON desde el frontend)
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
        insert_data = {'nombre': nombre, 'fecha': fecha, 'hora': hora_para_db, 'completada': False, 'recordatorio': recordatorio}
        response = supabase.from_('cita').insert(insert_data).execute()
        new_cita = response.data[0]
        return jsonify({'id': new_cita['id'], 'nombre': new_cita['nombre'], 'fecha': new_cita['fecha'], 'hora': new_cita['hora'], 'completada': new_cita['completada'], 'recordatorio': new_cita.get('recordatorio')}), 201
    except Exception as e:
        print(f"Error al añadir cita a Supabase: {e}")
        return jsonify({'error': f'Error al añadir cita: {str(e)}'}), 500

@app.route('/api/citas/all', methods=['GET'])
def get_all_citas():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        # Incluir 'recordatorio' en la declaración de selección
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada,recordatorio').order('fecha').order('hora').execute()
        citas = response.data
        return jsonify([
            {
                'id': cita['id'],
                'nombre': cita['nombre'],
                'fecha': cita['fecha'],
                'hora': cita['hora'],
                'completada': cita['completada'],
                'recordatorio': cita.get('recordatorio') # Incluir recordatorio
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
        # Incluir 'recordatorio' en la declaración de selección
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada,recordatorio').eq('fecha', fecha).order('hora').execute()
        citas = response.data
        return jsonify([
            {
                'id': cita['id'],
                'nombre': cita['nombre'],
                'fecha': cita['fecha'],
                'hora': cita['hora'],
                'completada': cita['completada'],
                'recordatorio': cita.get('recordatorio') # Incluir recordatorio
            } for cita in citas
        ])
    except Exception as e:
        print(f"Error al obtener citas por fecha de Supabase: {e}")
        return jsonify({'error': f'Error al obtener citas por fecha: {str(e)}'}), 500

@app.route('/api/citas/<int:year>/<int:month>', methods=['GET'])
def get_citas_for_month(year, month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    
    # Calcular el primer y último día del mes
    start_date = date(year, month, 1)
    end_date = date(year, month, calendar.monthrange(year, month)[1]) # Obtener el último día del mes

    try:
        # Filtrar citas dentro del rango del mes
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada,recordatorio').gte('fecha', str(start_date)).lte('fecha', str(end_date)).order('fecha').order('hora').execute()
        citas = response.data

        processed_citas = []
        today = date.today()

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
                'recordatorio': cita.get('recordatorio') # Incluir recordatorio
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
    # Obtener todas las citas desde la fecha actual en adelante, ordenadas por fecha y hora
    try:
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada,recordatorio').gte('fecha', str(today)).order('fecha').order('hora').execute()
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
                'recordatorio': cita.get('recordatorio') # Incluir recordatorio
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
        # Incluir 'recordatorio' en la declaración de selección
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada,recordatorio').eq('id', str(cita_id)).limit(1).execute()
        cita = response.data[0] if response.data else None
        if not cita:
            return jsonify({'error': 'Cita no encontrada.'}), 404
        return jsonify({
            'id': cita['id'],
            'nombre': cita['nombre'],
            'fecha': cita['fecha'],
            'hora': cita['hora'],
            'completada': cita['completada'],
            'recordatorio': cita.get('recordatorio') # Incluir recordatorio
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
    # NUEVO: Obtener lista de requisitos (ya cadena JSON desde el frontend)
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
        update_data = {'nombre': nombre, 'fecha': fecha, 'hora': hora_para_db, 'recordatorio': recordatorio}
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

# NUEVA RUTA: Alternar el estado de completado de un requisito individual
@app.route('/api/citas/<uuid:cita_id>/toggle_requisito_completado', methods=['PATCH'])
def toggle_requisito_completado(cita_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    requisito_index = data.get('index')

    if not isinstance(requisito_index, int):
        return jsonify({'error': 'El índice del requisito es obligatorio y debe ser un entero.'}), 400

    try:
        # Obtener la cita actual para obtener su recordatorio
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
                return jsonify({'error': 'Formato de recordatorio inválido.'}), 400

        if not (0 <= requisito_index < len(requisitos)):
            return jsonify({'error': 'Índice de requisito inválido.'}), 400

        # Alternar el estado 'checked' para el requisito especificado
        requisitos[requisito_index]['checked'] = not requisitos[requisito_index]['checked']

        # Convertir de nuevo a cadena JSON para guardar en Supabase
        updated_recordatorio_json_str = json.dumps(requisitos)

        # Actualizar la cita con el nuevo recordatorio
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

# --- NUEVAS RUTAS API para Supermercados ---
@app.route('/api/supermarkets', methods=['POST'])
def add_supermarket():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    name = data.get('name')

    if not name:
        return jsonify({'error': 'El nombre del supermercado es obligatorio.'}), 400
    
    try:
        # Intentar insertar el nuevo supermercado
        response = supabase.from_('supermarkets').insert({"name": name}).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        # Capturar errores de duplicación (ej., restricción UNIQUE)
        if "duplicate key value violates unique constraint" in str(e):
            return jsonify({'error': 'Ya existe un supermercado con ese nombre.'}), 409 # Conflicto
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
@app.route('/api/ingredients', methods=['POST'])
def add_ingredient():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    name = data.get('name')
    calories_per_100g = data.get('calories_per_100g')
    proteins_per_100g = data.get('proteins_per_100g')
    carbs_per_100g = data.get('carbs_per_100g')
    fats_per_100g = data.get('fats_per_100g')
    cantidad_estandar = data.get('cantidad_estandar')
    unidad_medida = data.get('unidad_medida')

    # Valores predeterminados si no se proporcionan
    calories_per_100g = calories_per_100g if calories_per_100g is not None else 0.0
    proteins_per_100g = proteins_per_100g if proteins_per_100g is not None else 0.0
    carbs_per_100g = carbs_per_100g if carbs_per_100g is not None else 0.0
    fats_per_100g = fats_per_100g if fats_per_100g is not None else 0.0
    cantidad_estandar = cantidad_estandar if cantidad_estandar is not None else 0.0
    unidad_medida = unidad_medida if unidad_medida is not None else ''

    if not name:
        return jsonify({'error': 'El nombre del ingrediente es obligatorio.'}), 400
    
    # NUEVA VALIDACIÓN: Si cantidad_estandar es 0, no permitir si se espera un precio por unidad.
    # Aunque la lógica de precios se gestiona en ingredient_prices, es bueno que el ingrediente base
    # tenga una cantidad_estandar válida si se va a usar para cálculos de precios unitarios.
    # Por ahora, permitimos 0, pero si esto causa problemas en el frontend, se podría hacer obligatorio.
    # if cantidad_estandar <= 0 and (calories_per_100g > 0 or proteins_per_100g > 0 or carbs_per_100g > 0 or fats_per_100g > 0):
    #     return jsonify({'error': 'La cantidad estándar debe ser mayor que 0 si se proporcionan valores nutricionales.'}), 400


    try:
        # Comprobar si el ingrediente ya existe para evitar duplicaciones
        existing_ingredient_response = supabase.from_('ingredients').select('id, name').eq('name', name).limit(1).execute()
        if existing_ingredient_response.data:
            # Si el ingrediente ya existe, devolver un mensaje informativo
            return jsonify({'message': 'El ingrediente ya existe.', 'id': existing_ingredient_response.data[0]['id'], 'existing': True}), 200

        insert_data = {
            'name': name,
            'calories_per_100g': calories_per_100g,
            'proteins_per_100g': proteins_per_100g,
            'carbs_per_100g': carbs_per_100g,
            'fats_per_100g': fats_per_100g,
            'cantidad_estandar': cantidad_estandar,
            'unidad_medida': unidad_medida
        }
        response = supabase.from_('ingredients').insert(insert_data).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        print(f"Error al añadir ingrediente a Supabase: {e}")
        return jsonify({'error': f'Error al añadir ingrediente: {str(e)}'}), 500

@app.route('/api/ingredients', methods=['GET'])
def get_ingredients():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        # Obtener todos los ingredientes
        ingredients_response = supabase.from_('ingredients').select('*').order('name').execute()
        # No verificamos ingredients_response.error directamente aquí, ya que el atributo puede no existir
        # si la respuesta es exitosa pero sin datos, o si es un objeto de tipo genérico.
        # Cualquier error real de Supabase debería lanzar una excepción capturada por el 'except Exception as e'.
        
        ingredients_data = ingredients_response.data

        # Para cada ingrediente, obtener sus precios de la tabla ingredient_prices
        ingredients_with_prices = []
        for ingredient in ingredients_data:
            # Asegurarse de que el ingredient['id'] es una cadena antes de usarlo en .eq()
            ingredient_id_str = str(ingredient['id'])
            
            prices_response = supabase.from_('ingredient_prices').select('supermarket_id, price').eq('ingredient_id', ingredient_id_str).execute()
            
            # Similar a ingredients_response, no verificamos prices_response.error directamente
            # pero el 'except' general lo capturará si hay un problema fundamental.
            ingredient['prices'] = prices_response.data # Añadir la lista de precios al objeto ingrediente
            
            ingredients_with_prices.append(ingredient)

        return jsonify(ingredients_with_prices), 200
    except Exception as e:
        print(f"Error inesperado al obtener ingredientes de Supabase: {e}")
        # Optionally, print the full traceback for more context
        traceback.print_exc()
        return jsonify({'error': f'Error inesperado al obtener ingredientes: {str(e)}'}), 500

@app.route('/api/ingredients/<uuid:ingredient_id>', methods=['PUT', 'DELETE'])
def handle_ingredient(ingredient_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503

    try:
        # Lógica para PUT (actualizar un ingrediente por ID)
        if request.method == 'PUT':
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Datos de actualización requeridos.'}), 400

            update_data = {
                'name': data.get('name'),
                'calories_per_100g': float(data['calories_per_100g']) if data.get('calories_per_100g') is not None else None,
                'proteins_per_100g': float(data['proteins_per_100g']) if data.get('proteins_per_100g') is not None else None,
                'carbs_per_100g': float(data['carbs_per_100g']) if data.get('carbs_per_100g') is not None else None,
                'fats_per_100g': float(data['fats_per_100g']) if data.get('fats_per_100g') is not None else None,
                'cantidad_estandar': float(data['cantidad_estandar']) if data.get('cantidad_estandar') is not None else None,
                'unidad_medida': data.get('unidad_medida') if data.get('unidad_medida') is not None else None
            }

            # Filtrar valores None para que Supabase no intente actualizarlos si no se proporcionaron
            update_data_filtered = {k: v for k, v in update_data.items() if v is not None}

            update_response = supabase.from_('ingredients').update(update_data_filtered).eq('id', str(ingredient_id)).execute()

            if not update_response.data:
                return jsonify({'error': 'Ingrediente no encontrado o no se pudo actualizar.'}), 404

            return jsonify(update_response.data[0]), 200

        # Lógica para DELETE (eliminar un ingrediente por ID)
        elif request.method == 'DELETE':
            # Antes de eliminar el ingrediente, eliminar sus precios asociados
            supabase.from_('ingredient_prices').delete().eq('ingredient_id', str(ingredient_id)).execute()
            
            delete_response = supabase.from_('ingredients').delete().eq('id', str(ingredient_id)).execute()
            if not delete_response.data:
                return jsonify({'error': 'Ingrediente no encontrado.'}), 404
            return jsonify({'message': 'Ingrediente y sus precios eliminados exitosamente.'}), 200

    except Exception as e:
        print(f"Error en la operación del ingrediente ({request.method}): {e}")
        return jsonify({'error': f'Error en la operación del ingrediente: {str(e)}'}), 500

# --- NUEVAS RUTAS para Precios de Ingredientes (ingredient_prices) ---
@app.route('/api/ingredients/<uuid:ingredient_id>/prices', methods=['POST'])
def add_ingredient_price(ingredient_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    supermarket_id = data.get('supermarket_id')
    price = data.get('price')

    if not supermarket_id or price is None:
        return jsonify({'error': 'El ID del supermercado y el precio son obligatorios.'}), 400
    if not isinstance(price, (int, float)) or price < 0:
        return jsonify({'error': 'El precio debe ser un número válido y no negativo.'}), 400

    try:
        # Verificar si el ingrediente existe
        ingredient_check = supabase.from_('ingredients').select('id').eq('id', str(ingredient_id)).limit(1).execute()
        if not ingredient_check.data:
            return jsonify({'error': 'Ingrediente no encontrado.'}), 404

        # Verificar si el supermercado existe
        supermarket_check = supabase.from_('supermarkets').select('id').eq('id', str(supermarket_id)).limit(1).execute()
        if not supermarket_check.data:
            return jsonify({'error': 'Supermercado no encontrado.'}), 404

        # Intentar insertar el precio
        insert_data = {
            'ingredient_id': str(ingredient_id),
            'supermarket_id': str(supermarket_id),
            'price': price
        }
        response = supabase.from_('ingredient_prices').insert(insert_data).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        if "duplicate key value violates unique constraint" in str(e):
            return jsonify({'error': 'Ya existe un precio para este ingrediente en este supermercado.'}), 409
        print(f"Error al añadir precio de ingrediente a Supabase: {e}")
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
    ingredients = data.get('ingredients') # Esto ya debe ser una lista de dicts
    total_cost = data.get('total_cost')
    total_calories = data.get('total_calories')
    total_proteins = data.get('proteins_per_100g') # Corrected: should be total_proteins
    total_carbs = data.get('total_carbs')
    total_fats = data.get('total_fats')

    if not name or not ingredients:
        return jsonify({'error': 'El nombre y los ingredientes de la receta son obligatorios.'}), 400

    # Convertir la lista de ingredientes a JSON string para almacenar en la DB
    ingredients_json_str = json.dumps(ingredients)

    try:
        insert_data = {
            'name': name,
            'description': description,
            'ingredients': ingredients_json_str,
            'total_cost': total_cost if total_cost is not None else 0.0,
            'total_calories': total_calories if total_calories is not None else 0.0,
            'total_proteins': total_proteins if total_proteins is not None else 0.0,
            'total_carbs': total_carbs if total_carbs is not None else 0.0,
            'total_fats': total_fats if total_fats is not None else 0.0
        }
        response = supabase.from_('recipes').insert(insert_data).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        print(f"Error al añadir receta a Supabase: {e}")
        return jsonify({'error': f'Error al añadir receta: {str(e)}'}), 500

@app.route('/api/recipes', methods=['GET'])
def get_recipes():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('recipes').select('*').order('name').execute()
        
        # Parsear la cadena JSON de ingredientes de vuelta a un objeto Python
        recipes_list = []
        for recipe in response.data:
            recipe_copy = recipe.copy()
            if isinstance(recipe_copy.get('ingredients'), str): # Asegurarse de que sea string antes de parsear
                try:
                    recipe_copy['ingredients'] = json.loads(recipe_copy['ingredients'])
                except json.JSONDecodeError:
                    recipe_copy['ingredients'] = [] # En caso de error de formato JSON
            else: # Si ya es un objeto JSON (ej. si se almacenó directamente como JSONB)
                recipe_copy['ingredients'] = recipe_copy.get('ingredients', [])
            
            recipes_list.append(recipe_copy)
        
        return jsonify(recipes_list), 200
    except Exception as e:
        print(f"Error al obtener recetas de Supabase: {e}")
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
        'total_calories': float(data['total_calories']) if data.get('total_calories') is not None else None,
        'total_proteins': float(data['total_proteins']) if data.get('total_proteins') is not None else None,
        'total_carbs': float(data['total_carbs']) if data.get('total_carbs') is not None else None,
        'total_fats': float(data['total_fats']) if data.get('total_fats') is not None else None # Corrected typo from fats_per_100g to total_fats
    }
    
    # Manejar los ingredientes como JSON
    ingredients = data.get('ingredients')
    if ingredients is not None:
        update_data['ingredients'] = json.dumps(ingredients)

    # Filtrar valores None
    update_data_filtered = {k: v for k, v in update_data.items() if v is not None}

    if not update_data_filtered:
        return jsonify({'error': 'No se proporcionaron datos para la actualización.'}), 400

    try:
        response = supabase.from_('recipes').update(update_data_filtered).eq('id', str(recipe_id)).execute()
        if not response.data:
            return jsonify({'error': 'Receta no encontrada o no se pudo actualizar.'}), 404
        
        updated_recipe = response.data[0]
        # Asegurarse de que los ingredientes se devuelvan como objeto JSON
        if isinstance(updated_recipe.get('ingredients'), str):
            updated_recipe['ingredients'] = json.loads(updated_recipe['ingredients'])
        return jsonify(updated_recipe), 200
    except Exception as e:
        print(f"Error al actualizar receta en Supabase: {e}")
        return jsonify({'error': f'Error al actualizar receta: {str(e)}'}), 500


# API para Menú Semanal (Singleton)
@app.route('/api/weekly_menu', methods=['GET'])
def get_weekly_menu():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        # Asumimos que solo hay una fila para el menú semanal
        response = supabase.from_('weekly_menu').select('*').limit(1).execute()
        menu_data = response.data[0] if response.data else None

        if menu_data and isinstance(menu_data.get('menu'), str):
            menu_data['menu'] = json.loads(menu_data['menu']) # Parsear el JSON string a objeto Python
        
        return jsonify(menu_data), 200
    except Exception as e:
        print(f"Error al obtener el menú semanal de Supabase: {e}")
        return jsonify({'error': f'Error al obtener el menú semanal: {str(e)}'}), 500

@app.route('/api/weekly_menu', methods=['PUT']) # Cambiado a PUT para semántica de actualización
def update_weekly_menu():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    menu = data.get('menu') # Esto ya debe ser el objeto JSON del menú

    if not menu:
        return jsonify({'error': 'Los datos del menú son obligatorios.'}), 400
    
    menu_json_str = json.dumps(menu)

    try:
        # Intentar obtener el menú existente (asumiendo un ID fijo o un solo registro)
        existing_menu_response = supabase.from_('weekly_menu').select('id').limit(1).execute()
        existing_menu_id = existing_menu_response.data[0]['id'] if existing_menu_response.data else None

        if existing_menu_id:
            # Actualizar el menú existente
            update_response = supabase.from_('weekly_menu').update({'menu': menu_json_str}).eq('id', existing_menu_id).execute()
            updated_menu = update_response.data[0]
            if isinstance(updated_menu.get('menu'), str):
                updated_menu['menu'] = json.loads(updated_menu['menu'])
            return jsonify(updated_menu), 200
        else:
            # Insertar un nuevo menú si no existe
            insert_response = supabase.from_('weekly_menu').insert({'menu': menu_json_str}).execute()
            new_menu = insert_response.data[0]
            if isinstance(new_menu.get('menu'), str):
                new_menu['menu'] = json.loads(new_menu['menu'])
            return jsonify(new_menu), 201
            
    except Exception as e:
        print(f"Error al actualizar/añadir menú semanal en Supabase: {e}")
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
        # Ordenar por fecha descendente
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

# Punto de entrada de la aplicación
if __name__ == '__main__':
    # Es crucial que estas funciones se ejecuten al inicio para la lógica diaria
    init_db_supabase()
    generate_tasks_for_today_from_routines()
    manage_overdue_tasks()
    
    # Puerto para la aplicación Flask (Render usará el puerto que le indiques en sus settings, ej. 10000)
    # En desarrollo local, puedes usar el puerto predeterminado 5000 o cambiarlo aquí.
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
