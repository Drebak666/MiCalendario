import os
import json
from datetime import datetime, date, timedelta
# Importamos el cliente de Supabase
from supabase import create_client, Client
from flask import Flask, render_template, request, jsonify, g

app = Flask(__name__)

# --- Configuración de Supabase ---
# Es CRUCIAL usar variables de entorno para las credenciales.
# Render te permite configurar estas variables en su Dashboard.
SUPABASE_URL = "https://ugpqqmcstqtywyrzfnjq.supabase.co" # EJEMPLO: "https://ugpqqmcstqtywyrzfnjq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVncHFxbWNzdHF0eXd5cnpmbmpxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk3Mzk2ODgsImV4cCI6MjA2NTMxNTY4OH0.nh56rQQliOnX5AZzePaZv_RB05uRIlUbfQPkWJPvKcE" # EJEMPLO: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

supabase: Client = None # Inicializamos supabase como None para manejar la conexión

# Bloque de inicialización de Supabase
if not SUPABASE_URL or not SUPABASE_KEY:
    # Esto se ejecutará si las variables de entorno no están configuradas.
    # Es vital configurar SUPABASE_URL y SUPABASE_KEY en Render.
    print("[ERROR] Fallo crítico al conectar o inicializar Supabase:")
    print("[ERROR] Asegúrate de que tus credenciales de Supabase (URL y Key) sean correctas en las variables de entorno de Render.")
    print("[ERROR] Si estás ejecutando localmente, asegúrate de que las variables de entorno estén configuradas (ej. con un archivo .env).")
    # No salimos de la aplicación aquí, pero las operaciones de DB fallarán.
else:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase conectado y cliente inicializado correctamente.")
    except Exception as e:
        print(f"[ERROR] Fallo crítico al conectar o inicializar Supabase: {e}")
        # Aquí puedes decidir qué hacer si la conexión inicial falla (ej. salir o deshabilitar funcionalidades de DB).

# --- Funciones de Utilidad (Adaptadas para Supabase) ---

# Nota: Las funciones get_db y close_connection de SQLite ya no son necesarias para Supabase
# Se eliminan ya que el cliente de Supabase se maneja directamente.

def init_db_supabase():
    """
    Función para inicializar la base de datos en Supabase.
    Ya no crea tablas, solo inserta datos por defecto si es necesario.
    Las tablas deben ser creadas manualmente en el Dashboard de Supabase.
    """
    if supabase is None:
        print("[ADVERTENCIA] Supabase no está inicializado. No se pueden insertar tipos de registro por defecto.")
        return

    try:
        # Verificar si la tabla 'tipo_registro' está vacía
        response = supabase.from_('tipo_registro').select('count', count='exact').execute()
        count = response.count

        if count == 0:
            print("Insertando tipos de registro por defecto en Supabase...")
            default_types = [
                {"nombre": "General"}, {"nombre": "Salud"}, {"nombre": "Cita"},
                {"nombre": "Escolar"}, {"nombre": "Personal"}, {"nombre": "Finanzas"},
                {"nombre": "Documento"}, {"nombre": "Trabajo"}, {"nombre": "Hogar"},
                {"nombre": "Ocio"}, {"nombre": "Deporte"}, {"nombre": "Emergencia"}
            ]
            
            # Insertar en bloques si hay muchos, pero para 12 es directo
            insert_response = supabase.from_('tipo_registro').insert(default_types).execute()
            if insert_response.data:
                print(f"Tipos de registro por defecto insertados: {len(insert_response.data)}.")
            else:
                print("No se insertaron tipos de registro por defecto o hubo un error.")
        else:
            print(f"La tabla 'tipo_registro' ya contiene {count} datos.")

    except Exception as e:
        print(f"[ERROR] Error al inicializar/insertar tipos de registro en Supabase: {e}")

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
    # Si tus días en Supabase son 0=Dom, 1=Lun:
    today_day_of_week_html_format = (today_day_of_week_py + 1) % 7 # Lunes (0) -> 1, Domingo (6) -> 0

    print(f"[{datetime.now()}] Iniciando generación de tareas para hoy ({today_date_str}, día de la semana HTML: {today_day_of_week_html_format}) desde rutinas.")

    try:
        # Obtener rutinas de Supabase
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
                    routine_days = json.loads(dias_semana_raw) # Asumiendo que dias_semana es TEXT/JSONB
                    if not isinstance(routine_days, list): # Asegurar que es una lista
                        routine_days = []
                except (json.JSONDecodeError, TypeError):
                    print(f"Error: No se pudo decodificar dias_semana para la rutina {routine_id}: {dias_semana_raw}. Saltando esta rutina.")
                    continue

            if today_day_of_week_html_format in routine_days:
                # Verificar si la tarea ya existe para hoy
                existing_task_response = supabase.from_('tarea').select('id').eq('fecha', today_date_str).eq('texto', routine_name).eq('hora', routine_time).execute()
                existing_task = existing_task_response.data

                if not existing_task:
                    # Insertar la nueva tarea
                    new_task_data = {
                        'fecha': today_date_str,
                        'texto': routine_name,
                        'hora': routine_time,
                        'completada': False # Supabase BOOLEAN type
                    }
                    insert_response = supabase.from_('tarea').insert(new_task_data).execute()
                    if insert_response.data:
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
        # Eliminar tareas completadas de días anteriores
        delete_response = supabase.from_('tarea').delete().lt('fecha', today_str).eq('completada', True).execute()
        deleted_count = len(delete_response.data) if delete_response.data else 0
        print(f"[{datetime.now()}] Eliminadas {deleted_count} tareas completadas de días anteriores.")

        # Mover tareas incompletas de días anteriores al día actual
        update_response = supabase.from_('tarea').update({'fecha': today_str}).lt('fecha', today_str).eq('completada', False).execute()
        moved_count = len(update_response.data) if update_response.data else 0
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
        tareas = response.data
        return jsonify([
            {
                'id': tarea['id'],
                'fecha': tarea['fecha'],
                'texto': tarea['texto'],
                'completada': tarea['completada'], # Supabase ya devuelve booleanos
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
    search_pattern = f"{year}-{month_str}-" # Usamos LIKE para el patrón

    try:
        # Supabase no tiene una función 'DISTINCT' directa en el cliente Python para select simple,
        # pero podemos usar el filtro y luego procesar en Python o usar RLS
        # Más eficiente sería:
        # response = supabase.rpc('get_distinct_fechas_tareas', {'year_param': year, 'month_param': month}).execute()
        # Pero eso requeriría una función de BD. Más simple es:
        response = supabase.from_('tarea').select('fecha').ilike('fecha', f'{search_pattern}%').execute()
        
        # Obtener valores únicos en Python
        fechas = sorted(list(set([row['fecha'] for row in response.data])))
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
        # Supabase inserta y devuelve el objeto completo, incluyendo el ID generado
        insert_data = {'fecha': fecha, 'texto': texto, 'hora': hora_para_db, 'completada': False}
        response = supabase.from_('tarea').insert(insert_data).execute()
        new_tarea = response.data[0] # El primer elemento es el objeto insertado

        return jsonify({'id': new_tarea['id'], 'fecha': new_tarea['fecha'], 'texto': new_tarea['texto'], 'completada': new_tarea['completada'], 'hora': new_tarea['hora']}), 201
    except Exception as e:
        print(f"Error al añadir tarea a Supabase: {e}")
        return jsonify({'error': f'Error al añadir tarea: {str(e)}'}), 500

@app.route('/api/tareas/<uuid:tarea_id>/toggle_completada', methods=['PATCH'])
def toggle_tarea_completada(tarea_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        # Obtener estado actual
        response = supabase.from_('tarea').select('completada').eq('id', str(tarea_id)).limit(1).execute()
        tarea = response.data[0] if response.data else None

        if not tarea:
            return jsonify({'error': 'Tarea no encontrada.'}), 404

        new_state = not tarea['completada'] # Invertir el estado booleano
        
        # Actualizar en Supabase
        update_response = supabase.from_('tarea').update({'completada': new_state}).eq('id', str(tarea_id)).execute()
        
        if not update_response.data: # Si no hay datos actualizados, es que no se encontró
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
        
        if not delete_response.data: # Si data está vacía, no se eliminó nada
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
        
        if not update_response.data:
            return jsonify({"error": "Tarea no encontrada para aplazar"}), 404
        return jsonify({"message": "Tarea aplazada con éxito."}), 200
    except Exception as e:
        print(f"Error de base de datos al aplazar tarea en Supabase: {e}")
        return jsonify({'error': f'Error de base de datos al aplazar: {str(e)}'}), 500

# --- RUTAS API para Registros Importantes (Adaptadas para Supabase) ---

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
            'imagen_base64': imagen_base64
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
        response = supabase.from_('registro_importante').select('id,fecha,titulo,descripcion,tipo,imagen_base64').order('fecha', desc=True).order('id', desc=True).execute()
        registros = response.data
        return jsonify([
            {
                'id': registro['id'],
                'fecha': registro['fecha'],
                'titulo': registro['titulo'],
                'descripcion': registro['descripcion'],
                'tipo': registro['tipo'],
                'imagen_base64': registro['imagen_base64']
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
        fechas = sorted(list(set([row['fecha'] for row in response.data])))
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
        print(f"Error al obtener tipos de registro desde Supabase: {e}")
        return jsonify({'error': f'Error al obtener tipos de registro: {str(e)}'}), 500

# --- RUTAS API para Rutinas (Adaptadas para Supabase) ---

@app.route('/api/rutinas', methods=['POST'])
def add_rutina():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.json
    nombre = data.get('nombre')
    hora = data.get('hora')
    dias = data.get('dias') # Esto debería ser una lista de enteros, ej. [0, 1, 2]

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
        # Convertir la lista de días a JSON string para almacenar en TEXT/JSONB
        dias_semana_json = json.dumps(dias)
        insert_data = {'nombre': nombre, 'hora': hora_para_db, 'dias_semana': dias_semana_json}
        response = supabase.from_('rutina').insert(insert_data).execute()
        new_rutina = response.data[0]

        return jsonify({'id': new_rutina['id'], 'nombre': new_rutina['nombre'], 'hora': new_rutina['hora'], 'dias': dias}), 201
    except Exception as e:
        print(f"Error al añadir rutina a Supabase: {e}")
        return jsonify({'error': f'Error al añadir rutina: {str(e)}'}), 500

@app.route('/api/rutinas', methods=['GET'])
def get_rutinas():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('rutina').select('id,nombre,hora,dias_semana').order('id', desc=True).execute()
        rutinas = response.data
        
        rutinas_list = []
        for rutina in rutinas:
            raw_dias_semana = rutina['dias_semana']
            dias_semana_list = []
            if raw_dias_semana: # Verificar si no es None o vacío
                try:
                    dias_semana_list = json.loads(raw_dias_semana)
                    if not isinstance(dias_semana_list, list):
                        dias_semana_list = []
                except (json.JSONDecodeError, TypeError):
                    dias_semana_list = []
                    print(f"Advertencia: No se pudo decodificar o el tipo es incorrecto para dias_semana de rutina {rutina['id']}. Valor: {raw_dias_semana}")

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
        if not delete_response.data:
            return jsonify({'error': 'Rutina no encontrada.'}), 404
        return jsonify({'message': 'Rutina eliminada exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar rutina de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar rutina: {str(e)}'}), 500

# --- Rutas API para Lista de la Compra (Adaptadas para Supabase) ---

@app.route('/api/lista_compra', methods=['GET'])
def get_lista_compra():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('lista_compra').select('id,item,comprado').order('id', desc=True).execute()
        items = response.data
        return jsonify([
            {
                'id': item['id'],
                'item': item['item'],
                'comprado': item['comprado'] # Supabase ya devuelve booleanos
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
        new_item = response.data[0]

        return jsonify({'id': new_item['id'], 'item': new_item['item'], 'comprado': new_item['comprado']}), 201
    except Exception as e:
        print(f"Error al añadir ítem a la lista de la compra en Supabase: {e}")
        return jsonify({'error': f'Error al añadir ítem: {str(e)}'}), 500

@app.route('/api/lista_compra/<uuid:item_id>/toggle_comprado', methods=['PATCH'])
def toggle_item_comprado(item_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('lista_compra').select('comprado').eq('id', str(item_id)).limit(1).execute()
        item = response.data[0] if response.data else None

        if not item:
            return jsonify({'error': 'Ítem no encontrado.'}), 404

        new_state = not item['comprado']
        update_response = supabase.from_('lista_compra').update({'comprado': new_state}).eq('id', str(item_id)).execute()
        
        if not update_response.data:
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
        if not delete_response.data:
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
        # Borra todos los elementos de la tabla 'lista_compra'
        delete_response = supabase.from_('lista_compra').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute() # Condición para eliminar todos los registros
        # Puedes revisar delete_response.count para saber cuántos elementos se eliminaron.
        return jsonify({'message': f'Lista de la compra borrada exitosamente. Se eliminaron {len(delete_response.data) if delete_response.data else 0} ítems.'}), 200
    except Exception as e:
        print(f"Error de base de datos al borrar toda la lista de la compra en Supabase: {e}")
        return jsonify({'error': f'Error de base de datos: {str(e)}'}), 500

# Punto de entrada de la aplicación
if __name__ == '__main__':
    # No es necesario llamar a init_db() de SQLite, ahora es init_db_supabase()
    # Y solo se encarga de insertar datos por defecto, no de crear tablas.
    init_db_supabase()
    generate_tasks_for_today_from_routines()
    manage_overdue_tasks()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

