import os
import json
from datetime import datetime, date, timedelta
from supabase import create_client, Client
from flask import Flask, render_template, request, jsonify, g, session
from functools import wraps
import uuid # Importar el módulo uuid
import calendar # Necesario para calendar.monthrange

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secreto_y_cambiar_en_produccion") # Clave secreta para sesiones

# --- Configuración de Supabase ---
# Es CRUCIAL usar variables de entorno para las credenciales en producción.
# Render te permite configurar estas variables en su Dashboard.
# Para desarrollo local, puedes configurarlas en tu entorno o usar un archivo .env.
SUPABASE_URL = "https://ugpqqmcstqtywyrzfnjq.supabase.co" # EJEMPLO: "https://ugpqqmcstqtywyrzfnjq.supabase.co"
# CAMBIA ESTA CLAVE por tu CLAVE SUPABASE (KEY: anon o service_role)
# Asegúrate de que sea la clave completa y correcta de tu panel de Supabase.
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVncHFxbWNzdHF0eXd5cnpmbmpxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk3Mzk2ODgsImV4cCI6MjA2NTMxNTY4OH0.nh56rQQliOnX5AZzePaZv_RB05uRIlUbfQPkWJPvKcE"

supabase: Client = None

def init_db_supabase():
    global supabase
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Conexión a Supabase establecida con éxito.")
    except Exception as e:
        print(f"Error al inicializar Supabase: {e}")
        supabase = None # Asegúrate de que Supabase sea None si falla la conexión

# Middleware para asegurar que Supabase esté disponible en cada solicitud si se usa.
@app.before_request
def before_request():
    if supabase is None:
        init_db_supabase() # Intentar reconectar si es None

# --- Funciones de autenticación (ya no usadas, pero la defición se mantiene) ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Esta función ya no impone autenticación en ninguna ruta del proyecto.
        # Si en el futuro quieres añadir autenticación a algunas páginas, puedes volver a añadir el decorador
        # en las rutas específicas y reintroducir la lógica de sesión o un sistema de autenticación real aquí.
        # if 'logged_in' not in session:
        #     return jsonify({'error': 'No autorizado. Se requiere autenticación.'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    pin = data.get('pin')
    # Este PIN es solo para demostración. En producción, usa un método de autenticación seguro.
    if pin == "1234": # ¡Cambia esto por un método seguro en producción!
        session['logged_in'] = True
        return jsonify({'message': 'Acceso concedido'}), 200
    else:
        return jsonify({'error': 'PIN incorrecto'}), 401

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return "Has cerrado sesión."

# --- Rutas de Renderizado de Páginas (TODAS SIN REQUERIR LOGIN) ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calendario')
def calendario():
    return render_template('calendario.html')

@app.route('/registros_importantes')
def registros_importantes():
    return render_template('registros_importantes.html')

@app.route('/alimentacion')
def alimentacion():
    return render_template('alimentacion.html')

@app.route('/documentacion')
def documentacion():
    return render_template('documentacion.html')

@app.route('/gimnasio')
def gimnasio():
    return render_template('gimnasio.html')

@app.route('/lista')
def lista_compra():
    # CORRECCIÓN: Asegurarse de que el nombre del template es 'lista.html'
    return render_template('lista.html')

@app.route('/citas')
def citas():
    return render_template('citas.html')

@app.route('/notas')
def notas():
    return render_template('notas.html')

# --- API para Tareas (Sin requerir login) ---
@app.route('/api/tareas', methods=['POST'])
def add_tarea():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    fecha = data.get('fecha')
    texto = data.get('texto')
    hora = data.get('hora')
    try:
        response = supabase.from_('tarea').insert({"fecha": fecha, "texto": texto, "hora": hora, "completada": False}).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tareas/<fecha>', methods=['GET'])
def get_tareas_por_fecha(fecha):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('tarea').select("*").eq('fecha', fecha).order('hora').execute()
        return jsonify(response.data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tareas/<uuid:tarea_id>/toggle_completada', methods=['PATCH'])
def toggle_tarea_completada(tarea_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        current_state_response = supabase.from_('tarea').select('completada').eq('id', str(tarea_id)).limit(1).execute()
        if not current_state_response.data:
            return jsonify({'error': 'Tarea no encontrada.'}), 404
        
        current_state = current_state_response.data[0]['completada']
        new_state = not current_state

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

@app.route('/api/tareas/<uuid:tarea_id>/aplazar', methods=['PATCH'])
def aplazar_tarea(tarea_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    new_fecha = data.get('new_fecha')
    new_hora = data.get('new_hora')
    
    if not new_fecha:
        return jsonify({'error': 'Nueva fecha es obligatoria.'}), 400

    try:
        update_data = {"fecha": new_fecha, "completada": False} # Al aplazar, se desmarca como completada
        if new_hora:
            update_data["hora"] = new_hora
        else:
            update_data["hora"] = None # Elimina la hora si no se proporciona

        response = supabase.from_('tarea').update(update_data).eq('id', str(tarea_id)).execute()
        
        if not response.data:
            return jsonify({'error': 'Tarea no encontrada o no se pudo actualizar.'}), 404

        return jsonify(response.data[0]), 200
    except Exception as e:
        print(f"Error al aplazar tarea en Supabase: {e}")
        return jsonify({'error': f'Error al aplazar tarea: {str(e)}'}), 500

@app.route('/api/tareas/dias_con_tareas/<int:year>/<int:month>', methods=['GET'])
def get_dias_con_tareas(year, month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]}" # Obtiene el último día del mes

        response = supabase.from_('tarea').select('fecha').gte('fecha', start_date).lte('fecha', end_date).execute()
        
        # Extraer solo las fechas y eliminar duplicados
        dates = sorted(list(set([item['fecha'] for item in response.data])))
        return jsonify(dates), 200
    except Exception as e:
        print(f"Error al obtener días con tareas: {e}")
        return jsonify({'error': f'Error al obtener días con tareas: {str(e)}'}), 500


# --- API para Rutinas (Sin requerir login) ---
@app.route('/api/rutinas', methods=['POST'])
def add_rutina():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    nombre = data.get('nombre')
    hora = data.get('hora')
    dias = data.get('dias') # Lista de números de día (0=Dom, 1=Lun...)
    try:
        response = supabase.from_('rutina').insert({"nombre": nombre, "hora": hora, "dias": dias}).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rutinas', methods=['GET'])
def get_rutinas():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('rutina').select("*").order('hora').execute()
        return jsonify(response.data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

@app.route('/api/rutinas/<uuid:rutina_id>/toggle_completada_dia', methods=['POST'])
def toggle_rutina_completada_dia(rutina_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    fecha_str = data.get('fecha')
    
    if not fecha_str:
        return jsonify({'error': 'Fecha es obligatoria.'}), 400

    try:
        check_response = supabase.from_('rutina_completada').select("*").eq('rutina_id', str(rutina_id)).eq('fecha', fecha_str).limit(1).execute()

        if check_response.data:
            supabase.from_('rutina_completada').delete().eq('rutina_id', str(rutina_id)).eq('fecha', fecha_str).execute()
            return jsonify({'id': str(rutina_id), 'fecha': fecha_str, 'completada': False}), 200
        else:
            supabase.from_('rutina_completada').insert({"rutina_id": str(rutina_id), "fecha": fecha_str}).execute()
            return jsonify({'id': str(rutina_id), 'fecha': fecha_str, 'completada': True}), 201
    except Exception as e:
        print(f"Error al cambiar estado de rutina completada por día en Supabase: {e}")
        return jsonify({'error': f'Error al actualizar rutina completada: {str(e)}'}), 500

@app.route('/api/rutinas/completadas_por_dia/<fecha>', methods=['GET'])
def get_rutinas_completadas_por_dia(fecha):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('rutina_completada').select('rutina_id').eq('fecha', fecha).execute()
        completed_ids = [item['rutina_id'] for item in response.data]
        return jsonify(completed_ids), 200
    except Exception as e:
        print(f"Error al obtener rutinas completadas por día: {e}")
        return jsonify({'error': f'Error al obtener rutinas completadas: {str(e)}'}), 500

def generate_tasks_for_today_from_routines():
    if supabase is None:
        print("Supabase no está disponible para generar tareas desde rutinas.")
        return

    today = date.today()
    today_weekday = today.weekday()
    supabase_weekday = today_weekday 

    print(f"DEBUG: Generando tareas para hoy {today} (día Supabase: {supabase_weekday})")

    try:
        last_run_date_response = supabase.from_('app_state').select('value').eq('key', 'last_routine_generation_date').limit(1).execute()
        last_run_date_str = last_run_date_response.data[0]['value'] if last_run_date_response.data else None
        
        if last_run_date_str == str(today):
            print("Tareas de rutina ya generadas para hoy. Saltando.")
            return
    except Exception as e:
        print(f"ADVERTENCIA: No se pudo verificar la última fecha de generación de rutinas: {e}. Procediendo con la generación.")


    try:
        all_routines_response = supabase.from_('rutina').select("*").execute()
        routines_to_generate = [
            r for r in all_routines_response.data
            if r['dias'] is not None and supabase_weekday in r['dias']
        ]


        for routine in routines_to_generate:
            existing_task_response = supabase.from_('tarea').select("*").eq('fecha', str(today)).eq('texto', routine['nombre']).limit(1).execute()
            if not existing_task_response.data:
                print(f"Creando tarea para rutina: {routine['nombre']} a las {routine['hora']}")
                supabase.from_('tarea').insert({
                    "fecha": str(today),
                    "texto": routine['nombre'],
                    "hora": routine['hora'],
                    "completada": False 
                }).execute()
            else:
                print(f"Tarea para rutina {routine['nombre']} ya existe para hoy. Saltando.")
        
        supabase.from_('app_state').upsert({'key': 'last_routine_generation_date', 'value': str(today)}).execute()

        print("Generación de tareas de rutina completada.")

    except Exception as e:
        print(f"Error en generate_tasks_for_today_from_routines: {e}")

def manage_overdue_tasks():
    if supabase is None:
        print("Supabase no está disponible para manejar tareas atrasadas.")
        return

    today = date.today()
    print(f"DEBUG: Gestionando tareas atrasadas antes de {today}")

    try:
        overdue_tasks_response = supabase.from_('tarea').select("*").lt('fecha', str(today)).eq('completada', False).execute()
        
        for task in overdue_tasks_response.data:
            print(f"DEBUG: Aplazando tarea atrasada '{task['texto']}' de {task['fecha']} a hoy.")
            supabase.from_('tarea').update({'fecha': str(today)}).eq('id', task['id']).execute()
        print("Gestión de tareas atrasadas completada.")
    except Exception as e:
        print(f"Error en manage_overdue_tasks: {e}")


# --- API para Citas (Sin requerir login) ---
@app.route('/api/citas', methods=['POST'])
def add_cita():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    nombre = data.get('nombre')
    fecha = data.get('fecha')
    hora = data.get('hora')
    try:
        response = supabase.from_('cita').insert({"nombre": nombre, "fecha": fecha, "hora": hora, "completada": False}).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/citas/proximas/<int:year>/<int:month>', methods=['GET'])
def get_proximas_citas(year, month):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        today = date.today()
        
        response = supabase.from_('cita').select("*").gte('fecha', str(today)).order('fecha').order('hora').execute()
        
        citas_data = response.data
        
        for cita in citas_data:
            cita_date = date.fromisoformat(cita['fecha'])
            delta = cita_date - today
            cita['dias_restantes'] = delta.days
        
        return jsonify(citas_data), 200
    except Exception as e:
        print(f"Error al obtener próximas citas: {e}")
        return jsonify({'error': f'Error al obtener próximas citas: {str(e)}'}), 500

@app.route('/api/citas/<fecha>', methods=['GET'])
def get_citas_por_fecha(fecha):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('cita').select("*").eq('fecha', fecha).order('hora').execute()
        return jsonify(response.data), 200
    except Exception as e:
        print(f"Error al obtener citas por fecha: {e}")
        return jsonify({'error': f'Error al obtener citas por fecha: {str(e)}'}), 500

# Ruta para obtener *todas* las citas
@app.route('/api/citas/all_citas', methods=['GET'])
def get_all_citas():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('cita').select("*").order('fecha').order('hora').execute()
        return jsonify(response.data), 200
    except Exception as e:
        print(f"Error al obtener todas las citas: {e}")
        return jsonify({'error': f'Error al obtener todas las citas: {str(e)}'}), 500


@app.route('/api/citas/<uuid:cita_id>/toggle_completada', methods=['PATCH'])
def toggle_cita_completada(cita_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        current_state_response = supabase.from_('cita').select('completada').eq('id', str(cita_id)).limit(1).execute()
        if not current_state_response.data:
            return jsonify({'error': 'Cita no encontrada.'}), 404
        
        current_state = current_state_response.data[0]['completada']
        new_state = not current_state

        update_response = supabase.from_('cita').update({'completada': new_state}).eq('id', str(cita_id)).execute()
        
        if not update_response.data:
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
        if not delete_response.data:
            return jsonify({'error': 'Cita no encontrada.'}), 404
        return jsonify({'message': 'Cita eliminada exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar cita de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar cita: {str(e)}'}), 500

# --- API para Registros Importantes (¡SIN REQUERIR LOGIN!) ---
@app.route('/api/tipos_registro', methods=['GET'])
def get_tipos_registro():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('tipo_registro').select("*").order('nombre').execute()
        return jsonify(response.data), 200
    except Exception as e:
        print(f"Error al obtener tipos de registro de Supabase: {e}")
        return jsonify({'error': f'Error al obtener tipos de registro: {str(e)}'}), 500

@app.route('/api/registros_importantes', methods=['GET'])
def get_all_registros_importantes():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('registro_importante').select("*").order('fecha', desc=True).execute()
        return jsonify(response.data), 200
    except Exception as e:
        print(f"Error al obtener registros importantes de Supabase: {e}")
        return jsonify({'error': f'Error al obtener registros importantes: {str(e)}'}), 500

@app.route('/api/registros_importantes/<uuid:registro_id>', methods=['DELETE'])
def delete_registro_importante(registro_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('registro_importante').delete().eq('id', str(registro_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Registro no encontrado.'}), 404
        return jsonify({'message': 'Registro eliminado exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar registro importante de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar registro importante: {str(e)}'}), 500

@app.route('/api/registros_importantes/add_from_task', methods=['POST'])
def add_registro_from_task():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    fecha = data.get('fecha')
    titulo = data.get('titulo')
    descripcion = data.get('descripcion')
    tipo = data.get('tipo', 'General')
    imagen_base64 = data.get('imagen_base64')
    nombre_archivo = data.get('nombre_archivo')
    mime_type = data.get('mime_type')

    if not fecha or not titulo:
        return jsonify({'error': 'Fecha y título son obligatorios.'}), 400

    try:
        insert_data = {
            "fecha": fecha,
            "titulo": titulo,
            "descripcion": descripcion,
            "tipo": tipo
        }
        if imagen_base64:
            insert_data["imagen_base64"] = imagen_base64
            insert_data["nombre_archivo"] = nombre_archivo
            insert_data["mime_type"] = mime_type

        response = supabase.from_('registro_importante').insert([insert_data]).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        print(f"Error al añadir registro importante desde tarea a Supabase: {e}")
        return jsonify({'error': f'Error al añadir registro importante: {str(e)}'}), 500


# --- API para Lista de Compra (Sin requerir login) ---
@app.route('/api/lista_compra', methods=['POST'])
def add_item_lista_compra():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    item_text = data.get('item')
    if not item_text:
        return jsonify({'error': 'El ítem no puede estar vacío.'}), 400
    try:
        response = supabase.from_('lista_compra').insert({"item": item_text, "comprado": False}).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        print(f"Error al añadir ítem a lista de compra: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/lista_compra', methods=['GET'])
def get_lista_compra():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        # La columna 'created_at' está definida en el SQL proporcionado.
        response = supabase.from_('lista_compra').select("*").order('created_at', desc=False).execute()
        return jsonify(response.data), 200
    except Exception as e:
        print(f"Error al obtener lista de compra: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/lista_compra/<uuid:item_id>/toggle_completado', methods=['PATCH'])
def toggle_item_lista_compra_completado(item_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        current_state_response = supabase.from_('lista_compra').select('comprado').eq('id', str(item_id)).limit(1).execute()
        if not current_state_response.data:
            return jsonify({'error': 'Ítem no encontrado.'}), 404
        
        current_state = current_state_response.data[0]['comprado']
        new_state = not current_state

        update_response = supabase.from_('lista_compra').update({'comprado': new_state}).eq('id', str(item_id)).execute()
        
        if not update_response.data:
            return jsonify({'error': 'Ítem no encontrado o no se pudo actualizar.'}), 404

        return jsonify({'id': str(item_id), 'comprado': new_state}), 200
    except Exception as e:
        print(f"Error al cambiar estado de ítem de lista de compra: {e}")
        return jsonify({'error': f'Error al actualizar ítem: {str(e)}'}), 500

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
        print(f"Error al eliminar ítem de lista de compra: {e}")
        return jsonify({'error': f'Error al eliminar ítem: {str(e)}'}), 500

@app.route('/api/lista_compra/count_uncompleted', methods=['GET'])
def count_uncompleted_lista_compra():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('lista_compra').select("id", count='exact').eq('comprado', False).execute()
        return jsonify(response.count), 200
    except Exception as e:
        print(f"Error al contar ítems incompletos de lista de compra: {e}")
        return jsonify({'error': str(e)}), 500

# --- API para Notas (Sin requerir login) ---
@app.route('/api/notas', methods=['POST'])
def add_note():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    texto = data.get('texto')
    fecha = data.get('fecha', str(date.today()))
    if not texto:
        return jsonify({'error': 'El texto de la nota no puede estar vacío.'}), 400
    try:
        response = supabase.from_('nota_rapida').insert({"texto": texto, "fecha": fecha}).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        print(f"Error al añadir nota rápida: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/notas', methods=['GET'])
def get_notes():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        # La columna 'created_at' está definida en el SQL proporcionado para nota_rapida.
        response = supabase.from_('nota_rapida').select("*").order('fecha', desc=True).order('created_at', desc=True).execute()
        return jsonify(response.data), 200
    except Exception as e:
        print(f"Error al obtener notas rápidas: {e}")
        return jsonify({'error': f'Error al obtener notas rápidas: {str(e)}'}), 500

@app.route('/api/notas/<uuid:note_id>', methods=['DELETE'])
def delete_note(note_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('nota_rapida').delete().eq('id', str(note_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Nota no encontrada.'}), 404
        return jsonify({'message': 'Nota eliminada exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar nota rápida: {e}")
        return jsonify({'error': f'Error al eliminar nota: {str(e)}'}), 500

@app.route('/api/notas/count', methods=['GET'])
def count_notes():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('nota_rapida').select("id", count='exact').execute()
        return jsonify(response.count), 200
    except Exception as e:
        print(f"Error al contar notas rápidas: {e}")
        return jsonify({'error': str(e)}), 500

# --- API para Documentación ---
@app.route('/api/documentacion', methods=['GET', 'POST'])
def get_or_add_documentos():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    
    if request.method == 'POST':
        data = request.get_json()
        fecha = data.get('fecha')
        titulo = data.get('titulo')
        descripcion = data.get('descripcion')
        tipo = data.get('tipo')
        imagen_base64 = data.get('imagen_base64')
        nombre_archivo = data.get('nombre_archivo')
        mime_type = data.get('mime_type')

        if not titulo:
            return jsonify({'error': 'El título del documento es obligatorio.'}), 400

        try:
            insert_data = {
                "fecha": fecha if fecha else str(date.today()),
                "titulo": titulo,
                "descripcion": descripcion,
                "tipo": tipo
            }
            if imagen_base64:
                insert_data["imagen_base64"] = imagen_base64
                insert_data["nombre_archivo"] = nombre_archivo
                insert_data["mime_type"] = mime_type

            response = supabase.from_('documento').insert([insert_data]).execute()
            return jsonify(response.data[0]), 201
        except Exception as e:
            print(f"Error al guardar documento: {e}")
            return jsonify({'error': f'Error al guardar documento: {str(e)}'}), 500
    
    elif request.method == 'GET':
        try:
            # Aquí es donde cargamos los documentos reales de la tabla 'documento'
            # Asegúrate de que esta tabla exista en tu Supabase.
            response = supabase.from_('documento').select("*").order('fecha', desc=True).order('created_at', desc=True).execute()
            return jsonify(response.data), 200
        except Exception as e:
            print(f"Error al obtener documentos: {e}")
            return jsonify({'error': f'Error al obtener documentos: {str(e)}'}), 500


@app.route('/api/documentacion/<uuid:documento_id>', methods=['DELETE'])
def delete_documento(documento_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('documento').delete().eq('id', str(documento_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Documento no encontrado.'}), 404
        return jsonify({'message': 'Documento eliminado exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar documento de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar documento: {str(e)}'}), 500


# NUEVA RUTA: para obtener tipos de documento (si tu frontend la está llamando)
@app.route('/api/tipos_documento', methods=['GET'])
def get_tipos_documento():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        response = supabase.from_('tipo_registro').select("*").order('nombre').execute() 
        tipos_documento = [item['nombre'] for item in response.data]
        
        # Si no se encontraron tipos en la base de datos, devuelve una lista por defecto.
        if not tipos_documento:
            tipos_documento = ['General', 'Contrato', 'Factura', 'Recibo', 'Identificación', 'Otro']
            
        return jsonify(tipos_documento), 200
    except Exception as e:
        print(f"Error al obtener tipos de documento: {e}")
        return jsonify({'error': f'Error al obtener tipos de documento: {str(e)}'}), 500


# --- NUEVAS API para Supermercados ---
@app.route('/api/supermarkets', methods=['POST'])
def add_supermarket():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    name = data.get('name')

    if not name:
        return jsonify({'error': 'El nombre del supermercado es obligatorio.'}), 400
    
    try:
        # Intenta insertar el nuevo supermercado
        response = supabase.from_('supermarkets').insert({"name": name}).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        # Captura errores de duplicación (por ejemplo, UNIQUE constraint)
        if "duplicate key value violates unique constraint" in str(e):
            return jsonify({'error': 'Un supermercado con ese nombre ya existe.'}), 409 # Conflict
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


# --- API para Alimentación (Modificada para usar supermarket_id) ---
@app.route('/api/ingredients', methods=['POST'])
def add_ingredient():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
    name = data.get('name')
    # Cambiado a 'supermarket_id' que el frontend enviará (o el nombre si es un string)
    supermarket_value = data.get('supermarket') # Este será el NOMBRE del supermercado
    price_per_unit = data.get('price_per_unit')
    calories_per_100g = data.get('calories_per_100g')
    proteins_per_100g = data.get('proteins_per_100g')
    carbs_per_100g = data.get('carbs_per_100g')
    fats_per_100g = data.get('fats_per_100g')

    if not all([name, price_per_unit is not None, calories_per_100g is not None, proteins_per_100g is not None, carbs_per_100g is not None, fats_per_100g is not None]):
        return jsonify({'error': 'Faltan datos obligatorios del ingrediente.'}), 400

    supermarket_id = None
    if supermarket_value:
        try:
            # Buscar el ID del supermercado por su nombre
            supermarket_response = supabase.from_('supermarkets').select('id').eq('name', supermarket_value).single().execute()
            supermarket_id = supermarket_response.data['id']
        except Exception as e:
            print(f"Advertencia: Supermercado '{supermarket_value}' no encontrado o error al buscarlo: {e}")
            # Puedes optar por devolver un error o simplemente no asignar un supermarket_id
            # Para este caso, continuaremos sin asignar el ID si no se encuentra.
            supermarket_id = None


    try:
        insert_data = {
            'name': name,
            'supermarket_id': supermarket_id, # Usar el ID del supermercado
            'price_per_unit': price_per_unit,
            'calories_per_100g': calories_per_100g,
            'proteins_per_100g': proteins_per_100g,
            'carbs_per_100g': carbs_per_100g,
            'fats_per_100g': fats_per_100g
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
        # Realiza un JOIN implícito para obtener el nombre del supermercado
        response = supabase.from_('ingredients').select('*, supermarkets(name)').order('name').execute()
        
        # Mapea los resultados para incluir el nombre del supermercado directamente
        ingredients_with_supermarket_names = []
        for ingredient in response.data:
            supermarket_name = ingredient['supermarkets']['name'] if ingredient['supermarkets'] else None
            ingredients_with_supermarket_names.append({
                'id': ingredient['id'],
                'name': ingredient['name'],
                'supermarket': supermarket_name, # Aquí usamos el nombre para el frontend
                'price_per_unit': ingredient['price_per_unit'],
                'calories_per_100g': ingredient['calories_per_100g'],
                'proteins_per_100g': ingredient['proteins_per_100g'],
                'carbs_per_100g': ingredient['carbs_per_100g'],
                'fats_per_100g': ingredient['fats_per_100g']
            })
        return jsonify(ingredients_with_supermarket_names), 200
    except Exception as e:
        print(f"Error al obtener ingredientes de Supabase: {e}")
        return jsonify({'error': f'Error al obtener ingredientes: {str(e)}'}), 500

@app.route('/api/ingredients/<uuid:ingredient_id>', methods=['DELETE'])
def delete_ingredient(ingredient_id):
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    try:
        delete_response = supabase.from_('ingredients').delete().eq('id', str(ingredient_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Ingrediente no encontrado.'}), 404
        return jsonify({'message': 'Ingrediente eliminado exitosamente.'}), 200
    except Exception as e:
        print(f"Error al eliminar ingrediente de Supabase: {e}")
        return jsonify({'error': f'Error al eliminar ingrediente: {str(e)}'}), 500

@app.route('/api/recipes', methods=['POST'])
def add_recipe():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
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
    try:
        delete_response = supabase.from_('recipes').delete().eq('id', str(recipe_id)).execute()
        if not delete_response.data:
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
    # Constante para el ID del menú semanal (para un solo usuario)
    WEEKLY_MENU_SINGLETON_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11" 
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
    data = request.get_json()
    menu_data = data.get('menu') # Esto será el diccionario del menú semanal

    if menu_data is None:
        return jsonify({'error': 'Los datos del menú son obligatorios.'}), 400
    # Constante para el ID del menú semanal (para un solo usuario)
    WEEKLY_MENU_SINGLETON_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11" 
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

# --- API para Gimnasio (PLACEHOLDER) ---
# Estas rutas son ejemplos y necesitarán ser completadas con la lógica de base de datos
# real una vez que definas la estructura para los registros de gimnasio.

@app.route('/api/gym_logs', methods=['POST'])
def add_gym_log():
    if supabase is None:
        return jsonify({'error': 'Servicio de base de datos no disponible.'}), 503
    data = request.get_json()
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
    init_db_supabase()
    generate_tasks_for_today_from_routines()
    manage_overdue_tasks()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
