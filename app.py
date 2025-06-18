import os
import json
from datetime import datetime, date, timedelta
from supabase import create_client, Client
from flask import Flask, render_template, request, jsonify, g, session
from functools import wraps
import uuid # Importar el módulo uuid

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secreto_y_cambiar_en_produccion") # Clave secreta para sesiones

# --- Configuración de Supabase ---
# Es CRUCIAL usar variables de entorno para las credenciales en producción.
# Render te permite configurar estas variables en su Dashboard.
# Para desarrollo local, puedes configurarlas en tu entorno o usar un archivo .env.
SUPABASE_URL = "https://ugpqqmcstqtywyrzfnjq.supabase.co" # EJEMPLO: "https://ugpqqmcstqtywyrzfnjq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVncHFxbWNzdHF0eXd5cnpmbmpxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk3Mzk2ODgsImV4cCI6MjA2NTMxNTY4OH0.nh56rQQliOnX5AZzePaZv_RB05uRIlUbfQPkWJPvKcE"
supabase: Client = None 

if not SUPABASE_URL or not SUPABASE_KEY or SUPABASE_KEY == "TU_CLAVE_SUPABASE_AQUI_COMPLETA":
    print("[ERROR] Fallo crítico: Las variables de entorno SUPABASE_URL y/o SUPABASE_KEY no están configuradas correctamente.")
    print("[ERROR] Asegúrate de definirlas en tu entorno de despliegue (ej. Render) o localmente, o reemplazar el placeholder.")
else:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase conectado y cliente inicializado correctamente.")
    except Exception as e:
        print(f"[ERROR] Fallo crítico al conectar o inicializar Supabase: {e}")

# --- Constante para el ID del menú semanal (para un solo usuario) ---
# Este ID será usado para el único registro de menú semanal en la tabla `weekly_menu`.
WEEKLY_MENU_SINGLETON_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11" # Puedes usar cualquier UUID fijo


# --- Decorador de Autenticación Sencillo ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': 'No autorizado. Se requiere autenticación.'}), 401
        return f(*args, **kwargs)
    return decorated_function

# --- Funciones de Utilidad (Adaptadas para Supabase) ---

def init_db_supabase():
    """
    Función para inicializar la base de datos en Supabase.
    Solo inserta datos por defecto si es necesario (para tipo_registro y tipo_documento).
    Las tablas deben ser creadas manualmente en el Dashboard de Supabase.
    """
    if supabase is None:
        print("[ADVERTENCIA] Supabase no está inicializado. No se pueden insertar tipos de registro/documento por defecto.")
        return

    try:
        # Inicializar tipo_registro
        response = supabase.from_('tipo_registro').select('count', count='exact').execute()
        count_registro = response.count if response and hasattr(response, 'count') else 0
        if count_registro == 0:
            print("Insertando tipos de registro por defecto en Supabase...")
            default_types_registro = [
                {"nombre": "General"}, {"nombre": "Salud"}, {"nombre": "Cita"},
                {"nombre": "Escolar"}, {"nombre": "Personal"}, {"nombre": "Finanzas"},
                {"nombre": "Documento"}, {"nombre": "Trabajo"}, {"nombre": "Hogar"},
                {"nombre": "Ocio"}, {"nombre": "Deporte"}, {"nombre": "Emergencia"}
            ]
            supabase.from_('tipo_registro').insert(default_types_registro).execute()
            print(f"Tipos de registro por defecto insertados: {len(default_types_registro)}.")
        else:
            print(f"La tabla 'tipo_registro' ya contiene {count_registro} datos.")
    except Exception as e:
        print(f"[ERROR] Error al inicializar/insertar tipos de registro en Supabase: {e}")

    try:
        # Inicializar tipo_documento
        response = supabase.from_('tipo_documento').select('count', count='exact').execute()
        count_documento = response.count if response and hasattr(response, 'count') else 0
        if count_documento == 0:
            print("Insertando tipos de documento por defecto en Supabase...")
            default_types_documento = [
                {"nombre": "Factura"}, {"nombre": "Contrato"}, {"nombre": "Recibo"},
                {"nombre": "Garantía"}, {"nombre": "Manual"}, {"nombre": "Identificación"},
                {"nombre": "Acuerdo"}, {"nombre": "Educación"}, {"nombre": "Salud"},
                {"nombre": "Vehículo"}, {"nombre": "Propiedad"}, {"nombre": "Otro"}
            ]
            supabase.from_('tipo_documento').insert(default_types_documento).execute()
            print(f"Tipos de documento por defecto insertados: {len(default_types_documento)}.")
        else:
            print(f"La tabla 'tipo_documento' ya contiene {count_documento} datos.")
    except Exception as e:
        print(f"[ERROR] Error al inicializar/insertar tipos de documento en Supabase: {e}")


def generate_tasks_for_today_from_routines():
    """
    Genera tareas para hoy a partir de rutinas, adaptado para Supabase.
    """
    if supabase is None:
        print("[ADVERTENCIA] Supabase no está inicializado. No se pueden generar tareas desde rutinas.")
        return

    today_date_str = datetime.now().strftime('%Y-%m-%d')
    today_day_of_week_py = datetime.now().weekday()
    # Mapeo a formato HTML (0=Dom, 1=Lun, ..., 6=Sab). Python weekday es 0=Lun, 6=Dom.
    today_day_of_week_html_format = (today_day_of_week_py + 1) % 7 # Lunes (0) -> 1, Domingo (6) -> 0

    print(f"[{datetime.now()}] Iniciando generación de tareas para hoy ({today_date_str}, día de la semana HTML: {today_day_of_week_html_format}) desde rutinas.")

    try:
        response = supabase.from_('rutina').select('id,nombre,hora,dias_semana').execute()
        routines = response.data if response and response.data else []

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
                existing_task = existing_task_response.data if existing_task_response and existing_task_response.data else []

                if not existing_task:
                    new_task_data = {
                        'fecha': today_date_str,
                        'texto': routine_name,
                        'hora': routine_time,
                        'completada': False
                    }
                    insert_response = supabase.from_('tarea').insert(new_task_data).execute()
                    if insert_response and insert_response.data:
                        print(f"[{datetime.now()}] Tarea '{routine_name}' generada para hoy desde rutina {routine_id}. ID: {insert_response.data[0]['id']}.")
                    else:
                        print(f"[{datetime.now()}] Fallo al generar tarea '{routine_name}' para hoy desde rutina {routine_id}.")
        print(f"[{datetime.now()}] Generación de tareas desde rutinas finalizada para hoy.")
    except Exception as e:
        print(f"[ERROR] Error en generate_tasks_for_today_from_routines: {e}")

def manage_overdue_tasks():
    """
    Gestiona tareas vencidas, adaptado para Supabase.
    """
    if supabase is None:
        print("[ADVERTENCIA] Supabase no está inicializado. No se pueden gestionar tareas vencidas.")
        return

    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f"[{datetime.now()}] Iniciando gestión de tareas vencidas para el día: {today_str}")

    try:
        delete_response = supabase.from_('tarea').delete().lt('fecha', today_str).eq('completada', True).execute()
        deleted_count = len(delete_response.data) if delete_response and delete_response.data else 0
        print(f"[{datetime.now()}] Eliminadas {deleted_count} tareas completadas de días anteriores.")

        update_response = supabase.from_('tarea').update({'fecha': today_str}).lt('fecha', today_str).eq('completada', False).execute()
        moved_count = len(update_response.data) if update_response and update_response.data else 0
        print(f"[{datetime.now()}] Movidas {moved_count} tareas incompletas de días anteriores al día actual.")

        print(f"[{datetime.now()}] Gestión de tareas vencidas finalizada.")
    except Exception as e:
        print(f"[ERROR] Error en manage_overdue_tasks: {e}")

# --- Rutas de la Aplicación (No necesitan cambios si solo renderizan HTML) ---

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

@app.route('/alimentacion') # Nueva ruta para la página de alimentación
def alimentacion_page():
    return render_template('alimentacion.html')

@app.route('/gimnasio') # Nueva ruta para la página de gimnasio
def gimnasio_page():
    # Asegúrate de que tienes un archivo gimnasio.html en tu carpeta templates
    return render_template('gimnasio.html')


# --- Rutas API para Autenticación ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    pin = data.get('pin')
    # ADVERTENCIA: PIN hardcodeado para demostración.
    # EN PRODUCCIÓN, utiliza un sistema de autenticación seguro (ej. Supabase Auth).
    if pin == '1234': 
        session['logged_in'] = True
        return jsonify({'message': 'Login exitoso'}), 200
    else:
        return jsonify({'error': 'PIN incorrecto'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    return jsonify({'message': 'Sesión cerrada'}), 200


# --- Rutas API para Tareas (Adaptadas para Supabase) ---

@app.route('/api/tareas/<string:fecha>', methods=['GET'])
def get_tareas_by_date(fecha):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido. Usa (YYYY-MM-DD)'}), 400

    try:
        response = supabase.from_('tarea').select('id,fecha,texto,completada,hora').eq('fecha', fecha).order('hora').order('texto').execute()
        tareas = response.data if response and response.data else []
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
        print(f"Error al obtener tareas por fecha desde Supabase: {e}")
        return jsonify({'error': f'Error al obtener tareas: {str(e)}'}), 500

@app.route('/api/tareas/dias_con_tareas/<int:year>/<int:month>', methods=['GET'])
def get_dias_con_tareas(year, month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    month_str = str(month).zfill(2)
    search_pattern = f"{year}-{month_str}-"

    try:
        response = supabase.from_('tarea').select('fecha').ilike('fecha', f'{search_pattern}%').execute()
        fechas = sorted(list(set([row['fecha'] for row in response.data]))) if response and response.data else []
        return jsonify(fechas)
    except Exception as e:
        print(f"Error al obtener días con tareas desde Supabase: {e}")
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
        return jsonify({'error': 'Fecha y texto de tarea son obligatorios.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
        if hora:
            datetime.strptime(hora, '%H:%M')
    except ValueError:
        return jsonify({'error': 'Formato de fecha u hora inválido. Usa (YYYY-MM-DD) y HH:MM'}), 400
    
    hora_para_db = hora if hora else None

    try:
        insert_data = {'fecha': fecha, 'texto': texto, 'hora': hora_para_db, 'completada': False}
        response = supabase.from_('tarea').insert(insert_data).execute()
        new_tarea = response.data[0] if response and response.data else None

        if new_tarea:
            return jsonify({'id': new_tarea['id'], 'fecha': new_tarea['fecha'], 'texto': new_tarea['texto'], 'completada': new_tarea['completada'], 'hora': new_tarea['hora']}), 201
        else:
            return jsonify({'error': 'No se pudo insertar la tarea en Supabase.'}), 500
    except Exception as e:
        print(f"Error al añadir tarea a Supabase: {e}")
        return jsonify({'error': f'Error al añadir tarea: {str(e)}'}), 500

@app.route('/api/tareas/<uuid:tarea_id>/toggle_completada', methods=['PATCH'])
def toggle_tarea_completada(tarea_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('tarea').select('completada').eq('id', str(tarea_id)).limit(1).execute()
        tarea = response.data[0] if response and response.data else None

        if not tarea:
            return jsonify({'error': 'Tarea no encontrada.'}), 404

        new_state = not tarea['completada']
        
        update_response = supabase.from_('tarea').update({'completada': new_state}).eq('id', str(tarea_id)).execute()
        
        if not update_response or not update_response.data:
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
        
        if not delete_response or not delete_response.data:
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
        return jsonify({"error": "Nueva fecha es obligatoria para aplazar."}), 400

    try:
        datetime.strptime(new_fecha, '%Y-%m-%d')
        if new_hora:
            datetime.strptime(new_hora, '%H:%M')
    except ValueError:
        return jsonify({'error': 'Formato de fecha u hora inválido. Usa (YYYY-MM-DD) y HH:MM'}), 400
    
    new_hora_for_db = new_hora if new_hora else None

    try:
        update_data = {'fecha': new_fecha, 'hora': new_hora_for_db, 'completada': False}
        update_response = supabase.from_('tarea').update(update_data).eq('id', str(task_id)).execute()
        
        if not update_response or not update_response.data:
            return jsonify({"error": "Tarea no encontrada para aplazar"}), 404
        return jsonify({"message": "Tarea aplazada con éxito."}), 200
    except Exception as e:
        print(f"Error de base de datos al aplazar tarea en Supabase: {e}")
        return jsonify({'error': f'Error de base de datos: {str(e)}'}), 500

# --- RUTAS API para Registros Importantes (Adaptadas para Supabase) ---
# Se elimina @login_required para hacerlas públicas, según la petición del usuario.
@app.route('/api/registros_importantes/add_from_task', methods=['POST'])
def add_registro_from_task():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json

    fecha = data.get('fecha')
    titulo = data.get('titulo')
    descripcion = data.get('descripcion')
    tipo = data.get('tipo') # Este será siempre "General" en el frontend nuevo
    imagen_base64 = data.get('imagen_base64') # Contiene la imagen o el archivo Base64
    nombre_archivo = data.get('nombre_archivo') # Nuevo: para guardar el nombre original del archivo
    mime_type = data.get('mime_type') # Nuevo: para guardar el tipo MIME del archivo

    if not fecha or not titulo:
        return jsonify({'error': 'Fecha y título son obligatorios para el registro importante.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except (ValueError, TypeError):
        return jsonify({'error': 'Formato de fecha inválido. Usa (YYYY-MM-DD)'}), 400

    try:
        insert_data = {
            'fecha': fecha,
            'titulo': titulo,
            'descripcion': descripcion,
            'tipo': tipo,
            'imagen_base664': imagen_base64, # Cambiado a imagen_base664 para coincidir con el campo de Supabase
            'nombre_archivo': nombre_archivo, # Guardar nombre del archivo
            'mime_type': mime_type # Guardar tipo MIME
        }
        response = supabase.from_('registro_importante').insert(insert_data).execute()
        new_registro = response.data[0] if response and response.data else None

        if new_registro:
            return jsonify({'message': 'Registro importante guardado', 'id': new_registro['id']}), 201
        else:
            return jsonify({'error': 'No se pudo insertar el registro importante en Supabase.'}), 500
    except Exception as e:
        print(f"Error al guardar registro importante en Supabase: {e}")
        return jsonify({'error': f'Error al guardar registro importante: {str(e)}'}), 500

@app.route('/api/registros_importantes', methods=['GET'])
def get_registros_importantes():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        # Añadir las nuevas columnas a la selección
        response = supabase.from_('registro_importante').select('id,fecha,titulo,descripcion,tipo,imagen_base664,nombre_archivo,mime_type').order('fecha', desc=True).order('id', desc=True).execute() # Cambiado a imagen_base664
        registros = response.data if response and response.data else []
        return jsonify([
            {
                'id': registro['id'],
                'fecha': registro['fecha'],
                'titulo': registro['titulo'],
                'descripcion': registro['descripcion'],
                'tipo': registro['tipo'],
                'imagen_base664': registro.get('imagen_base664'), # Cambiado a imagen_base664
                'nombre_archivo': registro.get('nombre_archivo'),
                'mime_type': registro.get('mime_type')
            } for registro in registros
        ])
    except Exception as e:
        print(f"Error al obtener registros importantes desde Supabase: {e}")
        return jsonify({'error': f'Error al obtener registros importantes: {str(e)}'}), 500

@app.route('/api/registros_importantes/dias_con_registros/<int:year>/<int:month>', methods=['GET'])
def get_dias_con_registros(year, month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    month_str = str(month).zfill(2)
    search_pattern = f"{year}-{month_str}-"

    try:
        response = supabase.from_('registro_importante').select('fecha').ilike('fecha', f'{search_pattern}%').execute()
        fechas = sorted(list(set([row['fecha'] for row in response.data]))) if response and response.data else []
        return jsonify(fechas)
    except Exception as e:
        print(f"Error al obtener días con registros desde Supabase: {e}")
        return jsonify({'error': f'Error al obtener días con registros: {str(e)}'}), 500

@app.route('/api/registros_importantes/<uuid:registro_id>', methods=['DELETE'])
def delete_registro_importante(registro_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('registro_importante').delete().eq('id', str(registro_id)).execute()
        if not delete_response or not delete_response.data:
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
        tipos = response.data if response and response.data else []
        return jsonify([
            {
                'id': tipo['id'],
                'nombre': tipo['nombre']
            } for tipo in tipos
        ])
    except Exception as e:
        print(f"Error al obtener tipos de registro desde Supabase: {e}")
        return jsonify({'error': f'Error al obtener tipos de registro: {str(e)}'}), 500

# --- RUTAS API para Documentación ---
@app.route('/api/documentacion', methods=['POST'])
@login_required # Protegida (asumimos que esta aún requiere login, según el app.py original)
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
        return jsonify({'error': 'Fecha y título son obligatorios para el documento.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except (ValueError, TypeError):
        return jsonify({'error': 'Formato de fecha inválido. Usa (YYYY-MM-DD)'}), 400

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
        new_documento = response.data[0] if response and response.data else None

        if new_documento:
            return jsonify({'message': 'Documento guardado', 'id': new_documento['id']}), 201
        else:
            return jsonify({'error': 'No se pudo insertar el documento en Supabase.'}), 500
    except Exception as e:
        print(f"Error al guardar documento en Supabase: {e}")
        return jsonify({'error': f'Error al guardar documento: {str(e)}'}), 500

@app.route('/api/documentacion', methods=['GET'])
@login_required # Protegida
def get_documentacion():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('documentacion').select('id,fecha,titulo,descripcion,tipo,imagen_base64,nombre_archivo,mime_type').order('fecha', desc=True).order('id', desc=True).execute()
        documentos = response.data if response and response.data else []
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
        print(f"Error al obtener documentación desde Supabase: {e}")
        return jsonify({'error': f'Error al obtener documentación: {str(e)}'}), 500

@app.route('/api/documentacion/dias_con_documentos/<int:year>/<int:month>', methods=['GET'])
@login_required # Protegida
def get_dias_con_documentos(year, month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    month_str = str(month).zfill(2)
    search_pattern = f"{year}-{month_str}-"

    try:
        response = supabase.from_('documentacion').select('fecha').ilike('fecha', f'{search_pattern}%').execute()
        fechas = sorted(list(set([row['fecha'] for row in response.data]))) if response and response.data else []
        return jsonify(fechas)
    except Exception as e:
        print(f"Error al obtener días con documentos desde Supabase: {e}")
        return jsonify({'error': f'Error al obtener días con documentos: {str(e)}'}), 500

@app.route('/api/documentacion/<uuid:documento_id>', methods=['DELETE'])
@login_required # Protegida
def delete_documento(documento_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('documentacion').delete().eq('id', str(documento_id)).execute()
        if not delete_response or not delete_response.data:
            return jsonify({'error': 'Documento no encontrado.'}), 404
        return jsonify({'message': 'Documento eliminado exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar documento de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar documento: {str(e)}'}), 500

@app.route('/api/tipos_documento', methods=['GET'])
@login_required # Protegida
def get_tipos_documento():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('tipo_documento').select('id,nombre').order('nombre').execute()
        tipos = response.data if response and response.data else []
        return jsonify([
            {
                'id': tipo['id'],
                'nombre': tipo['nombre']
            } for tipo in tipos
        ])
    except Exception as e:
        print(f"Error al obtener tipos de documento desde Supabase: {e}")
        return jsonify({'error': f'Error al obtener tipos de documento: {str(e)}'}), 500

# --- RUTAS API para Rutinas (Adaptadas para Supabase) ---

@app.route('/api/rutinas', methods=['POST'])
def add_rutina():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    nombre = data.get('nombre')
    hora = data.get('hora')
    dias = data.get('dias')

    if not nombre or not dias:
        return jsonify({'error': 'Nombre y días de la semana son obligatorios para la rutina.'}), 400
    
    if not isinstance(dias, list) or not all(isinstance(d, int) and 0 <= d <= 6 for d in dias):
        return jsonify({'error': 'Los días deben ser una lista de enteros entre 0 y 6.'}), 400

    if hora:
        try:
            datetime.strptime(hora, '%H:%M')
        except ValueError:
            return jsonify({'error': 'Formato de hora inválido. Usa HH:MM'}), 400

    hora_para_db = hora if hora else None

    try:
        dias_semana_json = json.dumps(dias)
        insert_data = {'nombre': nombre, 'hora': hora_para_db, 'dias_semana': dias_semana_json}
        response = supabase.from_('rutina').insert(insert_data).execute()
        new_rutina = response.data[0] if response and response.data else None

        if new_rutina:
            return jsonify({'id': new_rutina['id'], 'nombre': new_rutina['nombre'], 'hora': new_rutina['hora'], 'dias': dias}), 201
        else:
            return jsonify({'error': 'No se pudo insertar la rutina en Supabase.'}), 500
    except Exception as e:
        print(f"Error al añadir rutina a Supabase: {e}")
        return jsonify({'error': f'Error al añadir rutina: {str(e)}'}), 500

@app.route('/api/rutinas', methods=['GET'])
def get_rutinas():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('rutina').select('id,nombre,hora,dias_semana').order('id', desc=True).execute()
        rutinas = response.data if response and response.data else []
        
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
                'dias': dias_semana_list
            })
        return jsonify(rutinas_list)
    except Exception as e:
        print(f"Error al obtener rutinas desde Supabase: {e}")
        return jsonify({'error': f'Error al obtener rutinas: {str(e)}'}), 500

@app.route('/api/rutinas/<uuid:rutina_id>', methods=['DELETE'])
def delete_rutina(rutina_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('rutina').delete().eq('id', str(rutina_id)).execute()
        if not delete_response or not delete_response.data:
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
        completed_routine_ids = [item['rutina_id'] for item in response.data] if response and response.data else []
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
        
        if response and response.data:
            delete_response = supabase.from_('rutina_completada_dia').delete().eq('rutina_id', str(rutina_id)).eq('fecha_completado', fecha).execute()
            if not delete_response or not delete_response.data:
                raise Exception("No se pudo descompletar la rutina.")
            return jsonify({'message': 'Rutina marcada como incompleta para el día.'}), 200
        else:
            insert_data = {'rutina_id': str(rutina_id), 'fecha_completado': fecha}
            insert_response = supabase.from_('rutina_completada_dia').insert(insert_data).execute()
            if not insert_response or not insert_response.data:
                raise Exception("No se pudo completar la rutina.")
            return jsonify({'message': 'Rutina marcada como completada para el día.'}), 201
    except Exception as e:
        print(f"Error al cambiar estado de rutina por día: {e}")
        return jsonify({'error': f'Error al actualizar estado de rutina: {str(e)}'}), 500

# --- Rutas API para Lista de la Compra (Adaptadas para Supabase) ---

@app.route('/api/lista_compra', methods=['GET'])
def get_lista_compra():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('lista_compra').select('id,item,comprado').order('id', desc=True).execute()
        items = response.data if response and response.data else []
        return jsonify([
            {
                'id': item['id'],
                'item': item['item'],
                'comprado': item['comprado']
            } for item in items
        ])
    except Exception as e:
        print(f"Error al obtener lista de la compra desde Supabase: {e}")
        return jsonify({'error': f'Error al obtener lista de la compra: {str(e)}'}), 500

@app.route('/api/lista_compra', methods=['POST'])
def add_item_lista_compra():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    item_text = data.get('item')

    if not item_text:
        return jsonify({'error': 'El texto del ítem es obligatorio.'}), 400

    try:
        insert_data = {'item': item_text, 'comprado': False}
        response = supabase.from_('lista_compra').insert(insert_data).execute()
        new_item = response.data[0] if response and response.data else None

        if new_item:
            return jsonify({'id': new_item['id'], 'item': new_item['item'], 'comprado': new_item['comprado']}), 201
        else:
            return jsonify({'error': 'No se pudo insertar el ítem en la lista de la compra en Supabase.'}), 500
    except Exception as e:
        print(f"Error al añadir ítem a la lista de la compra en Supabase: {e}")
        return jsonify({'error': f'Error al añadir ítem: {str(e)}'}), 500

@app.route('/api/lista_compra/<uuid:item_id>/toggle_comprado', methods=['PATCH'])
def toggle_item_comprado(item_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('lista_compra').select('comprado').eq('id', str(item_id)).limit(1).execute()
        item = response.data[0] if response and response.data else None

        if not item:
            return jsonify({'error': 'Ítem no encontrado.'}), 404

        new_state = not item['comprado']
        update_response = supabase.from_('lista_compra').update({'comprado': new_state}).eq('id', str(item_id)).execute() 
        
        if not update_response or not update_response.data:
            return jsonify({'error': 'Ítem no encontrado o no se pudo actualizar.'}), 404

        return jsonify({'id': str(item_id), 'comprado': new_state}), 200
    except Exception as e:
        print(f"Error al cambiar estado del ítem en Supabase: {e}")
        return jsonify({'error': f'Error al cambiar estado del ítem: {str(e)}'}), 500

@app.route('/api/lista_compra/<uuid:item_id>', methods=['DELETE'])
def delete_item_lista_compra(item_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('lista_compra').delete().eq('id', str(item_id)).execute()
        if not delete_response or not delete_response.data:
            return jsonify({'error': 'Ítem no encontrado.'}), 404
        return jsonify({'message': 'Ítem eliminado exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar ítem de la lista de la compra en Supabase: {e}")
        return jsonify({'error': f'Error al eliminar ítem: {str(e)}'}), 500

@app.route('/api/lista_compra/clear_all', methods=['DELETE'])
def clear_all_items_lista_compra():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('lista_compra').delete().execute() 
        
        return jsonify({'message': f'Lista de la compra borrada exitosamente. Se eliminaron {len(delete_response.data) if delete_response and delete_response.data else 0} ítems.'}), 200
    except Exception as e:
        print(f"Error de base de datos al borrar toda la lista de la compra en Supabase: {e}")
        return jsonify({'error': f'Error de base de datos: {str(e)}'}), 500

# NUEVA RUTA: Contar ítems no completados de la lista de la compra
@app.route('/api/lista_compra/count_uncompleted', methods=['GET'])
# Se mantiene @login_required para este, según el app.py original (si es para el badge de navegación)
@login_required 
def count_uncompleted_list_items():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('lista_compra').select('count', count='exact').eq('comprado', False).execute()
        count = response.count if response and hasattr(response, 'count') else 0
        return jsonify(count), 200
    except Exception as e:
        print(f"Error al obtener el conteo de ítems no completados de la lista de la compra: {e}")
        return jsonify({'error': f'Error al obtener conteo: {str(e)}'}), 500


# --- NUEVAS RUTAS API para Notas Rápidas ---
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
        new_note = response.data[0] if response and response.data else None
        if new_note:
            return jsonify({'id': new_note['id'], 'texto': new_note['texto'], 'fecha': new_note['fecha']}), 201
        else:
            return jsonify({'error': 'No se pudo insertar la nota rápida en Supabase.'}), 500
    except Exception as e:
        print(f"Error al añadir nota rápida a Supabase: {e}")
        return jsonify({'error': f'Error al añadir nota: {str(e)}'}), 500

@app.route('/api/notas', methods=['GET'])
def get_notas_rapidas():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('nota_rapida').select('id,texto,fecha').order('fecha', desc=True).order('id', desc=True).execute()
        notas = response.data if response and response.data else []
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
        if not delete_response or not delete_response.data:
            return jsonify({'error': 'Nota no encontrada.'}), 404
        return jsonify({'message': 'Nota eliminada exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar nota rápida de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar nota: {str(e)}'}), 500

# NUEVA RUTA: Contar todas las notas rápidas
@app.route('/api/notas/count', methods=['GET'])
# Se mantiene @login_required para este, según el app.py original (si es para el badge de navegación)
@login_required 
def count_notes():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('nota_rapida').select('count', count='exact').execute()
        count = response.count if response and hasattr(response, 'count') else 0
        return jsonify(count), 200
    except Exception as e:
        print(f"Error al obtener el conteo de notas rápidas: {e}")
        return jsonify({'error': f'Error al obtener conteo: {str(e)}'}), 500


# --- NUEVAS RUTAS API para Citas ---
@app.route('/api/citas', methods=['POST'])
def add_cita():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    nombre = data.get('nombre')
    fecha = data.get('fecha')
    hora = data.get('hora')

    if not nombre or not fecha:
        return jsonify({'error': 'Nombre y fecha de la cita son obligatorios.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
        if hora:
            datetime.strptime(hora, '%H:%M')
    except ValueError:
        return jsonify({'error': 'Formato de fecha u hora inválido. Usa (YYYY-MM-DD) y HH:MM'}), 400
    
    hora_para_db = hora if hora else None

    try:
        insert_data = {'nombre': nombre, 'fecha': fecha, 'hora': hora_para_db, 'completada': False}
        response = supabase.from_('cita').insert(insert_data).execute()
        new_cita = response.data[0] if response and response.data else None
        if new_cita:
            return jsonify({'id': new_cita['id'], 'nombre': new_cita['nombre'], 'fecha': new_cita['fecha'], 'hora': new_cita['hora'], 'completada': new_cita['completada']}), 201
        else:
            return jsonify({'error': 'No se pudo insertar la cita en Supabase.'}), 500
    except Exception as e:
        print(f"Error al añadir cita a Supabase: {e}")
        return jsonify({'error': f'Error al añadir cita: {str(e)}'}), 500

@app.route('/api/citas/all', methods=['GET'])
def get_all_citas():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada').order('fecha').order('hora').execute()
        citas = response.data if response and response.data else []
        return jsonify([
            {
                'id': cita['id'],
                'nombre': cita['nombre'],
                'fecha': cita['fecha'],
                'hora': cita['hora'],
                'completada': cita['completada']
            } for cita in citas
        ])
    except Exception as e:
        print(f"Error al obtener todas las citas desde Supabase: {e}")
        return jsonify({'error': f'Error al obtener citas: {str(e)}'}), 500

@app.route('/api/citas/<string:fecha>', methods=['GET'])
def get_citas_by_date(fecha):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido. Usa (YYYY-MM-DD)'}), 400

    try:
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada').eq('fecha', fecha).order('hora').execute()
        citas = response.data if response and response.data else []
        return jsonify([
            {
                'id': cita['id'],
                'nombre': cita['nombre'],
                'fecha': cita['fecha'],
                'hora': cita['hora'],
                'completada': cita['completada']
            } for cita in citas
        ])
    except Exception as e:
        print(f"Error al obtener citas por fecha desde Supabase: {e}")
        return jsonify({'error': f'Error al obtener citas por fecha: {str(e)}'}), 500

@app.route('/api/citas/<int:year>/<int:int_month>', methods=['GET'])
def get_citas_for_month(year, int_month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    
    # Calcular el primer y último día del mes
    start_date = date(year, int_month, 1)
    end_date = date(year, int_month, 1) + timedelta(days=32) # Go a bit over to ensure last day of month
    end_date = end_date.replace(day=1) - timedelta(days=1) # Correctly get last day of month

    try:
        # Filtrar citas dentro del rango del mes
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada').gte('fecha', str(start_date)).lte('fecha', str(end_date)).order('fecha').order('hora').execute()
        citas = response.data if response and response.data else []

        processed_citas = []
        today = date.today()

        for cita in citas:
            cita_date = datetime.strptime(cita['fecha'], '%Y-%m-%d').date();
            diff_days = (cita_date - today).days;

            processed_citas.append({
                'id': cita['id'],
                'nombre': cita['nombre'],
                'fecha': cita['fecha'],
                'hora': cita['hora'],
                'completada': cita['completada'],
                'dias_restantes': diff_days
            })
        return jsonify(processed_citas)
    except Exception as e:
        print(f"Error al obtener citas para el mes desde Supabase: {e}")
        return jsonify({'error': f'Error al obtener citas para el mes: {str(e)}'}), 500

@app.route('/api/citas/proximas/<int:year>/<int:int_month>', methods=['GET']) # Cambiado 'month' a 'int_month' para evitar conflicto con la variable local 'month' en Supabase query
def get_proximas_citas(year, int_month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    
    today = datetime.now().date()
    
    try:
        # Primero, calculamos el primer y último día del mes actual para el filtro
        start_of_month = date(year, int_month, 1)
        # Calcular el último día del mes
        if int_month == 12:
            end_of_month = date(year, int_month, 31)
        else:
            end_of_month = date(year, int_month + 1, 1) - timedelta(days=1)

        response = supabase.from_('cita') \
                           .select('id,nombre,fecha,hora,completada') \
                           .gte('fecha', str(today)) \
                           .lte('fecha', str(end_of_month)) \
                           .order('fecha') \
                           .order('hora') \
                           .execute()
        citas = response.data if response and response.data else []

        processed_citas = []
        for cita in citas:
            cita_date = datetime.strptime(cita['fecha'], '%Y-%m-%d').date()
            diff_days = (cita_date - today).days

            # Solo incluir citas que caen en el mes consultado Y que sean >= hoy
            # Esto asegura que si estamos en Junio y pedimos citas de Junio, solo obtenemos las de Junio en adelante.
            if cita_date.month == int_month and cita_date.year == year:
                 processed_citas.append({
                    'id': cita['id'],
                    'nombre': cita['nombre'],
                    'fecha': cita['fecha'],
                    'hora': cita['hora'],
                    'completada': cita['completada'],
                    'dias_restantes': diff_days
                })
        # Ordenar nuevamente para asegurar que la "más próxima" sea la primera
        processed_citas.sort(key=lambda x: (x['fecha'], x['hora'] or '23:59'))
        return jsonify(processed_citas)
    except Exception as e:
        print(f"Error al obtener citas próximas desde Supabase: {e}")
        return jsonify({'error': f'Error al obtener citas próximas: {str(e)}'}), 500


@app.route('/api/citas/<uuid:cita_id>', methods=['GET'])
def get_cita_by_id(cita_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada').eq('id', str(cita_id)).limit(1).execute()
        cita = response.data[0] if response and response.data else None
        if not cita:
            return jsonify({'error': 'Cita no encontrada.'}), 404
        return jsonify({
            'id': cita['id'],
            'nombre': cita['nombre'],
            'fecha': cita['fecha'],
            'hora': cita['hora'],
            'completada': cita['completada']
        }), 200
    except Exception as e:
        print(f"Error al obtener cita por ID desde Supabase: {e}")
        return jsonify({'error': f'Error al obtener cita: {str(e)}'}), 500

@app.route('/api/citas/<uuid:cita_id>', methods=['PUT'])
def update_cita(cita_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    nombre = data.get('nombre')
    fecha = data.get('fecha')
    hora = data.get('hora')

    if not nombre or not fecha:
        return jsonify({'error': 'Nombre y fecha de la cita son obligatorios.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
        if hora:
            datetime.strptime(hora, '%H:%M')
    except ValueError:
        return jsonify({'error': 'Formato de fecha u hora inválido. Usa (YYYY-MM-DD) y HH:MM'}), 400
    
    hora_para_db = hora if hora else None

    try:
        update_data = {'nombre': nombre, 'fecha': fecha, 'hora': hora_para_db}
        update_response = supabase.from_('cita').update(update_data).eq('id', str(cita_id)).execute()
        
        if not update_response or not update_response.data:
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
        cita = response.data[0] if response and response.data else None

        if not cita:
            return jsonify({'error': 'Cita no encontrada.'}), 404

        new_state = not cita['completada']
        
        update_response = supabase.from_('cita').update({'completada': new_state}).eq('id', str(cita_id)).execute()
        
        if not update_response or not update_response.data:
            return jsonify({'error': 'Cita no encontrada o no se pudo actualizar.'}), 404

        return jsonify({'id': str(cita_id), 'completada': new_state}), 200
    except Exception as e:
        print(f"Error al cambiar estado de cita en Supabase: {e}")
        return jsonify({'error': f'Error al actualizar cita: {str(e)}'}), 500

@app.route('/api/citas/<uuid:cita_id>', methods=['DELETE'])
def delete_cita(cita_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('cita').delete().eq('id', str(cita_id)).execute()
        if not delete_response or not delete_response.data:
            return jsonify({'error': 'Cita no encontrada.'}), 404
        return jsonify({'message': 'Cita eliminada exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar cita de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar cita: {str(e)}'}), 500

# --- Rutas API para Alimentación ---

@app.route('/api/ingredients', methods=['POST'])
def add_ingredient():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    # userId ya no es necesario aquí para un solo usuario
    name = data.get('name')
    supermarket = data.get('supermarket')
    price_per_unit = data.get('price_per_unit')
    calories_per_100g = data.get('calories_per_100g')
    proteins_per_100g = data.get('proteins_per_100g')
    carbs_per_100g = data.get('carbs_per_100g')
    fats_per_100g = data.get('fats_per_100g')

    if not all([name, price_per_unit is not None, calories_per_100g is not None, proteins_per_100g is not None, carbs_per_100g is not None, fats_per_100g is not None]):
        return jsonify({'error': 'Faltan datos obligatorios del ingrediente.'}), 400

    try:
        insert_data = {
            'name': name,
            'supermarket': supermarket,
            'price_per_unit': price_per_unit,
            'calories_per_100g': calories_per_100g,
            'proteins_per_100g': proteins_per_100g,
            'carbs_per_100g': carbs_per_100g,
            'fats_per_100g': fats_per_100g
        }
        response = supabase.from_('ingredients').insert(insert_data).execute()
        new_ingredient = response.data[0] if response and response.data else None
        if new_ingredient:
            return jsonify(new_ingredient), 201
        else:
            return jsonify({'error': 'No se pudo insertar el ingrediente.'}), 500
    except Exception as e:
        print(f"Error al añadir ingrediente a Supabase: {e}")
        return jsonify({'error': f'Error al añadir ingrediente: {str(e)}'}), 500

@app.route('/api/ingredients', methods=['GET'])
def get_ingredients():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    # userId ya no es necesario para un solo usuario
    try:
        response = supabase.from_('ingredients').select('*').order('name').execute()
        ingredients = response.data if response and response.data else []
        return jsonify(ingredients), 200
    except Exception as e:
        print(f"Error al obtener ingredientes de Supabase: {e}")
        return jsonify({'error': f'Error al obtener ingredientes: {str(e)}'}), 500

@app.route('/api/ingredients/<uuid:ingredient_id>', methods=['DELETE'])
def delete_ingredient(ingredient_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    # userId ya no es necesario para un solo usuario
    try:
        delete_response = supabase.from_('ingredients').delete().eq('id', str(ingredient_id)).execute()
        if not delete_response or not delete_response.data:
            return jsonify({'error': 'Ingrediente no encontrado.'}), 404
        return jsonify({'message': 'Ingrediente eliminado exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar ingrediente de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar ingrediente: {str(e)}'}), 500

@app.route('/api/recipes', methods=['POST'])
def add_recipe():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    # userId ya no es necesario aquí para un solo usuario
    name = data.get('name')
    ingredients_list = data.get('ingredients') 
    total_cost = data.get('total_cost')
    total_calories = data.get('total_calories')
    total_proteins = data.get('total_proteins')
    total_carbs = data.get('total_carbs')
    total_fats = data.get('total_fats')

    if not all([name, ingredients_list is not None, total_cost is not None, total_calories is not None,
                total_proteins is not None, total_carbs is not None, total_fats is not None]):
        return jsonify({'error': 'Faltan datos obligatorios de la receta.'}), 400
    
    try:
        insert_data = {
            'name': name,
            'ingredients': ingredients_list, # Store as JSONB
            'total_cost': total_cost,
            'total_calories': total_calories,
            'total_proteins': total_proteins,
            'total_carbs': total_carbs,
            'total_fats': total_fats
        }
        response = supabase.from_('recipes').insert(insert_data).execute()
        new_recipe = response.data[0] if response and response.data else None
        if new_recipe:
            return jsonify(new_recipe), 201
        else:
            return jsonify({'error': 'No se pudo insertar la receta.'}), 500
    except Exception as e:
        print(f"Error al añadir receta a Supabase: {e}")
        return jsonify({'error': f'Error al añadir receta: {str(e)}'}), 500

@app.route('/api/recipes', methods=['GET'])
def get_recipes():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    # userId ya no es necesario para un solo usuario
    try:
        response = supabase.from_('recipes').select('*').order('name').execute()
        recipes = response.data if response and response.data else []
        return jsonify(recipes), 200
    except Exception as e:
        print(f"Error al obtener recetas de Supabase: {e}")
        return jsonify({'error': f'Error al obtener recetas: {str(e)}'}), 500

@app.route('/api/recipes/<uuid:recipe_id>', methods=['DELETE'])
def delete_recipe(recipe_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    # userId ya no es necesario para un solo usuario
    try:
        delete_response = supabase.from_('recipes').delete().eq('id', str(recipe_id)).execute()
        if not delete_response or not delete_response.data:
            return jsonify({'error': 'Receta no encontrada.'}), 404
        return jsonify({'message': 'Receta eliminada exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar receta de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar receta: {str(e)}'}), 500

@app.route('/api/weekly_menu', methods=['GET'])
def get_weekly_menu():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    # Obtener el menú semanal único
    try:
        response = supabase.from_('weekly_menu').select('menu').eq('id', WEEKLY_MENU_SINGLETON_ID).single().execute()
        menu_data = response.data['menu'] if response and response.data else {}
        return jsonify(menu_data), 200
    except Exception as e:
        # Si no existe, Supabase puede devolver un error. Lo tratamos como un menú vacío.
        print(f"Error al obtener menú semanal de Supabase (puede que no exista): {e}")
        return jsonify({}), 200 # Devolver diccionario vacío si no se encuentra o hay error

@app.route('/api/weekly_menu', methods=['PUT'])
def save_weekly_menu():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    menu_data = data.get('menu') # Esto será el diccionario del menú semanal

    if menu_data is None:
        return jsonify({'error': 'Los datos del menú son obligatorios.'}), 400

    try:
        # Usar upsert para insertar si no existe, o actualizar si existe el registro con el ID fijo.
        insert_data = {
            'id': WEEKLY_MENU_SINGLETON_ID,
            'menu': menu_data # Supabase almacena JSONB, por lo que puede manejar el diccionario directamente
        }
        # Asegúrate de que 'id' sea la clave primaria o tenga una restricción única para que upsert funcione.
        response = supabase.from_('weekly_menu').upsert(insert_data, on_conflict='id').execute()
        
        if response and response.data:
            return jsonify({'message': 'Menú semanal guardado con éxito.', 'menu': response.data[0]}), 200
        else:
            return jsonify({'error': 'No se pudo guardar el menú semanal.'}), 500
    except Exception as e:
        print(f"Error al guardar menú semanal en Supabase: {e}")
        return jsonify({'error': f'Error al guardar menú semanal: {str(e)}'}), 500

# --- Rutas API para Gimnasio (PLACEHOLDER) ---
# Estas rutas son ejemplos y necesitarán ser completadas con la lógica de base de datos
# real una vez que definas la estructura para los registros de gimnasio.

@app.route('/api/gym_logs', methods=['POST'])
def add_gym_log():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    # userId ya no es necesario aquí para un solo usuario
    # Añade validación y campos específicos para gym_log
    # Ejemplo: fecha, tipo_ejercicio, duracion, etc.

    try:
        # Aquí iría la lógica para insertar un nuevo registro de gimnasio en Supabase
        # Por ahora, solo un placeholder de éxito
        insert_data = {
            'message': 'Placeholder: Registro de gimnasio añadido',
            'timestamp': datetime.now().isoformat()
        }
        # response = supabase.from_('gym_logs').insert(insert_data).execute()
        return jsonify(insert_data), 201
    except Exception as e:
        print(f"Error al añadir registro de gimnasio: {e}")
        return jsonify({'error': f'Error al añadir registro de gimnasio: {str(e)}'}), 500

@app.route('/api/gym_logs', methods=['GET'])
def get_gym_logs():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    # userId ya no es necesario para un solo usuario
    try:
        # Aquí iría la lógica para obtener registros de gimnasio de Supabase
        # Por ahora, solo un placeholder vacío
        # response = supabase.from_('gym_logs').select('*').order('timestamp', desc=True).execute()
        return jsonify([]), 200
    except Exception as e:
        print(f"Error al obtener registros de gimnasio: {e}")
        return jsonify({'error': f'Error al obtener registros de gimnasio: {str(e)}'}), 500

@app.route('/api/gym_logs/<uuid:log_id>', methods=['DELETE'])
def delete_gym_log(log_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    # userId ya no es necesario para un solo usuario
    try:
        # Aquí iría la lógica para eliminar un registro de gimnasio de Supabase
        # Por ahora, solo un placeholder de éxito
        # delete_response = supabase.from_('gym_logs').delete().eq('id', str(log_id)).execute()
        return jsonify({'message': 'Placeholder: Registro de gimnasio eliminado.'}), 200
    except Exception as e:
        print(f"Error al eliminar registro de gimnasio: {e}")
        return jsonify({'error': f'Error al eliminar registro de gimnasio: {str(e)}'}), 500


# Punto de entrada de la aplicación
if __name__ == '__main__':
    # Es crucial que estas funciones se ejecuten al inicio para la lógica diaria
    init_db_supabase()
    generate_tasks_for_today_from_routines()
    manage_overdue_tasks()
    
    # Puerto para la aplicación Flask (Render usará el puerto 10000 por defecto)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
