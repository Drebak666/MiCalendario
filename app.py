import os
import json
from datetime import datetime, date, timedelta
from supabase import create_client, Client
from flask import Flask, render_template, request, jsonify, g, session
from functools import wraps
import uuid # Import the uuid module
import calendar # Necessary for calendar.monthrange, although not explicitly in the user's provided version, I add it for consistency if any function needs it.

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secreto_y_cambiar_en_produccion") # Secret key for sessions

# --- Supabase Configuration ---
# It is CRUCIAL to use environment variables for credentials in production.
# Render allows you to configure these variables in its Dashboard.
# For local development, you can configure them in your environment or use a .env file.
SUPABASE_URL = "https://ugpqqmcstqtywyrzfnjq.supabase.co" # EXAMPLE: "https://ugpqqmcstqtywyrzfnjq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVncHFxbWNzdHF0eXd5cnpmbmpxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk3Mzk2ODgsImV4cCI6MjA2NTMxNTY4OH0.nh56rQQliOnX5AZzePaZv_RB05uRIlUbfQPkWJPvKcE" # Make sure this is the complete and correct key from your Supabase panel.

supabase: Client = None 

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[ERROR] Critical failure: SUPABASE_URL and SUPABASE_KEY environment variables are not configured.")
    print("[ERROR] Make sure to define them in your deployment environment (e.g., Render) or locally.")
else:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase connected and client initialized successfully.")
    except Exception as e:
        print(f"[ERROR] Critical failure connecting or initializing Supabase: {e}")

# --- Simple Authentication Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': 'Unauthorized. Authentication required.'}), 401
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
        print("[WARNING] Supabase is not initialized. Cannot insert default record/document types.")
        return

    try:
        # Initialize tipo_registro
        response = supabase.from_('tipo_registro').select('count', count='exact').execute()
        count_registro = response.count
        if count_registro == 0:
            print("Inserting default record types into Supabase...")
            default_types_registro = [
                {"nombre": "General"}, {"nombre": "Salud"}, {"nombre": "Cita"},
                {"nombre": "Escolar"}, {"nombre": "Personal"}, {"nombre": "Finanzas"},
                {"nombre": "Documento"}, {"nombre": "Trabajo"}, {"nombre": "Hogar"},
                {"nombre": "Ocio"}, {"nombre": "Deporte"}, {"nombre": "Emergencia"}
            ]
            supabase.from_('tipo_registro').insert(default_types_registro).execute()
            print(f"Default record types inserted: {len(default_types_registro)}.")
        else:
            print(f"The 'tipo_registro' table already contains {count_registro} data.")
    except Exception as e:
        print(f"[ERROR] Error initializing/inserting record types in Supabase: {e}")

    try:
        # Initialize tipo_documento
        response = supabase.from_('tipo_documento').select('count', count='exact').execute()
        count_documento = response.count
        if count_documento == 0:
            print("Inserting default document types into Supabase...")
            default_types_documento = [
                {"nombre": "Factura"}, {"nombre": "Contrato"}, {"nombre": "Recibo"},
                {"nombre": "Garantía"}, {"nombre": "Manual"}, {"nombre": "Identificación"},
                {"nombre": "Acuerdo"}, {"nombre": "Educación"}, {"nombre": "Salud"},
                {"nombre": "Vehículo"}, {"nombre": "Propiedad"}, {"nombre": "Otro"}
            ]
            supabase.from_('tipo_documento').insert(default_types_documento).execute()
            print(f"Default document types inserted: {len(default_types_documento)}.")
        else:
            print(f"The 'tipo_documento' table already contains {count_documento} data.")
    except Exception as e:
        print(f"[ERROR] Error initializing/inserting document types in Supabase: {e}")


def generate_tasks_for_today_from_routines():
    """
    Generates tasks for today from routines, adapted for Supabase.
    """
    if supabase is None:
        print("[WARNING] Supabase is not initialized. Cannot generate tasks from routines.")
        return

    today_date_str = datetime.now().strftime('%Y-%m-%d')
    today_day_of_week_py = datetime.now().weekday()
    # Map to HTML format (0=Sun, 1=Mon, ..., 6=Sat). Python weekday is 0=Mon, 6=Sun.
    today_day_of_week_html_format = (today_day_of_week_py + 1) % 7 # Monday (0) -> 1, Sunday (6) -> 0

    print(f"[{datetime.now()}] Starting task generation for today ({today_date_str}, HTML day of week: {today_day_of_week_html_format}) from routines.")

    try:
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
                    print(f"Error: Could not decode dias_semana for routine {routine_id}: {dias_semana_raw}. Skipping this routine.")
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
                        print(f"[{datetime.now()}] Task '{routine_name}' generated for today from routine {routine_id}. ID: {insert_response.data[0]['id']}.")
                    else:
                        print(f"[{datetime.now()}] Failed to generate task '{routine_name}' for today from routine {routine_id}.")
        print(f"[{datetime.now()}] Task generation from routines finished for today.")
    except Exception as e:
        print(f"[ERROR] Error in generate_tasks_for_today_from_routines: {e}")

def manage_overdue_tasks():
    """
    Manages overdue tasks, adapted for Supabase.
    """
    if supabase is None:
        print("[WARNING] Supabase is not initialized. Cannot manage overdue tasks.")
        return

    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f"[{datetime.now()}] Starting overdue task management for the day: {today_str}")

    try:
        delete_response = supabase.from_('tarea').delete().lt('fecha', today_str).eq('completada', True).execute()
        deleted_count = len(delete_response.data) if delete_response.data else 0
        print(f"[{datetime.now()}] Deleted {deleted_count} completed tasks from previous days.")

        update_response = supabase.from_('tarea').update({'fecha': today_str}).lt('fecha', today_str).eq('completada', False).execute()
        moved_count = len(update_response.data) if update_response.data else 0
        print(f"[{datetime.now()}] Moved {moved_count} incomplete tasks from previous days to the current day.")

        print(f"[{datetime.now()}] Overdue task management finished.")
    except Exception as e:
        print(f"[ERROR] Error in manage_overdue_tasks: {e}")

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


# --- API Routes for Authentication ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    pin = data.get('pin')
    # WARNING: Hardcoded PIN for demonstration.
    # IN PRODUCTION, use a secure authentication system (e.g., Supabase Auth).
    if pin == '1234': 
        session['logged_in'] = True
        return jsonify({'message': 'Login successful'}), 200
    else:
        return jsonify({'error': 'Incorrect PIN'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    return jsonify({'message': 'Session closed'}), 200


# --- API Routes for Tasks (Adapted for Supabase) ---

@app.route('/api/tareas/<string:fecha>', methods=['GET'])
def get_tareas_by_date(fecha):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use (YYYY-MM-DD)'}), 400

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
        print(f"Error fetching tasks by date from Supabase: {e}")
        return jsonify({'error': f'Error fetching tasks: {str(e)}'}), 500

@app.route('/api/tareas/dias_con_tareas/<int:year>/<int:month>', methods=['GET'])
def get_dias_con_tareas(year, month):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    month_str = str(month).zfill(2)
    search_pattern = f"{year}-{month_str}-"

    try:
        response = supabase.from_('tarea').select('fecha').ilike('fecha', f'{search_pattern}%').execute()
        
        fechas = sorted(list(set([row['fecha'] for row in response.data])))
        return jsonify(fechas)
    except Exception as e:
        print(f"Error fetching days with tasks from Supabase: {e}")
        return jsonify({'error': f'Error fetching days with tasks: {str(e)}'}), 500

@app.route('/api/tareas', methods=['POST'])
def add_tarea():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    data = request.json
    fecha = data.get('fecha')
    texto = data.get('texto')
    hora = data.get('hora')

    if not fecha or not texto:
        return jsonify({'error': 'Task date and text are mandatory.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
        if hora:
            datetime.strptime(hora, '%H:%M')
    except ValueError:
        return jsonify({'error': 'Invalid date or time format. Use (YYYY-MM-DD) and HH:MM'}), 400
    
    hora_para_db = hora if hora else None

    try:
        insert_data = {'fecha': fecha, 'texto': texto, 'hora': hora_para_db, 'completada': False}
        response = supabase.from_('tarea').insert(insert_data).execute()
        new_tarea = response.data[0]

        return jsonify({'id': new_tarea['id'], 'fecha': new_tarea['fecha'], 'texto': new_tarea['texto'], 'completada': new_tarea['completada'], 'hora': new_tarea['hora']}), 201
    except Exception as e:
        print(f"Error adding task to Supabase: {e}")
        return jsonify({'error': f'Error adding task: {str(e)}'}), 500

@app.route('/api/tareas/<uuid:tarea_id>/toggle_completada', methods=['PATCH'])
def toggle_tarea_completada(tarea_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        response = supabase.from_('tarea').select('completada').eq('id', str(tarea_id)).limit(1).execute()
        tarea = response.data[0] if response.data else None

        if not tarea:
            return jsonify({'error': 'Task not found.'}), 404

        new_state = not tarea['completada']
        
        update_response = supabase.from_('tarea').update({'completada': new_state}).eq('id', str(tarea_id)).execute()
        
        if not update_response.data:
            return jsonify({'error': 'Task not found or could not be updated.'}), 404

        return jsonify({'id': str(tarea_id), 'completada': new_state}), 200
    except Exception as e:
        print(f"Error changing task status in Supabase: {e}")
        return jsonify({'error': f'Error updating task: {str(e)}'}), 500

@app.route('/api/tareas/<uuid:tarea_id>', methods=['DELETE'])
def delete_tarea(tarea_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        delete_response = supabase.from_('tarea').delete().eq('id', str(tarea_id)).execute()
        
        if not delete_response.data:
            return jsonify({'error': 'Task not found.'}), 404
        return jsonify({'message': 'Task deleted successfully.'}), 200
    except Exception as e:
        print(f"Error deleting task from Supabase: {e}")
        return jsonify({'error': f'Error deleting task: {str(e)}'}), 500

@app.route('/api/tareas/<uuid:task_id>/aplazar', methods=['PATCH'])
def aplazar_task(task_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    data = request.json
    new_fecha = data.get('new_fecha')
    new_hora = data.get('new_hora')

    if not new_fecha:
        return jsonify({"error": "New date is mandatory to postpone."}), 400

    try:
        datetime.strptime(new_fecha, '%Y-%m-%d')
        if new_hora:
            datetime.strptime(new_hora, '%H:%M')
    except ValueError:
        return jsonify({'error': 'Invalid date or time format. Use (YYYY-MM-DD) and HH:MM'}), 400
    
    new_hora_for_db = new_hora if new_hora else None

    try:
        update_data = {'fecha': new_fecha, 'hora': new_hora_for_db, 'completada': False}
        update_response = supabase.from_('tarea').update(update_data).eq('id', str(task_id)).execute()
        
        if not update_response.data:
            return jsonify({"error": "Task not found to postpone"}), 404
        return jsonify({"message": "Task postponed successfully."}), 200
    except Exception as e:
        print(f"Database error postponing task in Supabase: {e}")
        return jsonify({'error': f'Database error: {str(e)}'}), 500

# --- API Routes for Important Records (Adapted for Supabase) ---
# @login_required removed to make them public, as per user request.
@app.route('/api/registros_importantes/add_from_task', methods=['POST'])
def add_registro_from_task():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    data = request.json

    fecha = data.get('fecha')
    titulo = data.get('titulo')
    descripcion = data.get('descripcion')
    tipo = data.get('tipo') # This will always be "General" in the new frontend
    imagen_base64 = data.get('imagen_base64') # Contains the Base64 image or file
    nombre_archivo = data.get('nombre_archivo') # New: to save the original file name
    mime_type = data.get('mime_type') # New: to save the file MIME type

    if not fecha or not titulo:
        return jsonify({'error': 'Date and title are mandatory for the important record.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid date format. Use (YYYY-MM-DD)'}), 400

    try:
        insert_data = {
            'fecha': fecha,
            'titulo': titulo,
            'descripcion': descripcion,
            'tipo': tipo,
            'imagen_base64': imagen_base64,
            'nombre_archivo': nombre_archivo, # Save file name
            'mime_type': mime_type # Save MIME type
        }
        response = supabase.from_('registro_importante').insert(insert_data).execute()
        new_registro = response.data[0]

        return jsonify({'message': 'Important record saved', 'id': new_registro['id']}), 201
    except Exception as e:
        print(f"Error saving important record to Supabase: {e}")
        return jsonify({'error': f'Error saving important record: {str(e)}'}), 500

@app.route('/api/registros_importantes', methods=['GET'])
def get_registros_importantes():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        # Add new columns to the selection
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
        print(f"Error fetching important records from Supabase: {e}")
        return jsonify({'error': f'Error fetching important records: {str(e)}'}), 500

@app.route('/api/registros_importantes/dias_con_registros/<int:year>/<int:month>', methods=['GET'])
def get_dias_con_registros(year, month):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    month_str = str(month).zfill(2)
    search_pattern = f"{year}-{month_str}-"

    try:
        response = supabase.from_('registro_importante').select('fecha').ilike('fecha', f'{search_pattern}%').execute()
        fechas = sorted(list(set([row['fecha'] for row in response.data])))
        return jsonify(fechas)
    except Exception as e:
        print(f"Error fetching days with records from Supabase: {e}")
        return jsonify({'error': f'Error fetching days with records: {str(e)}'}), 500

@app.route('/api/registros_importantes/<uuid:registro_id>', methods=['DELETE'])
def delete_registro_importante(registro_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        delete_response = supabase.from_('registro_importante').delete().eq('id', str(registro_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Important record not found.'}), 404
        return jsonify({'message': 'Important record deleted successfully.'}), 200
    except Exception as e:
        print(f"Error deleting important record from Supabase: {e}")
        return jsonify({'error': f'Error deleting important record: {str(e)}'}), 500

@app.route('/api/tipos_registro', methods=['GET'])
def get_tipos_registro():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
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
        print(f"Error fetching record types from Supabase: {e}")
        return jsonify({'error': f'Error fetching record types: {str(e)}'}), 500

# --- API Routes for Documentation ---
@app.route('/api/documentacion', methods=['POST'])
@login_required # Protected (assuming this still requires login, as per original app.py)
def add_documento():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    data = request.json

    fecha = data.get('fecha')
    titulo = data.get('titulo')
    descripcion = data.get('descripcion')
    tipo = data.get('tipo')
    imagen_base64 = data.get('imagen_base64') 
    nombre_archivo = data.get('nombre_archivo')
    mime_type = data.get('mime_type')

    if not fecha or not titulo:
        return jsonify({'error': 'Date and title are mandatory for the document.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid date format. Use (YYYY-MM-DD)'}), 400

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

        return jsonify({'message': 'Document saved', 'id': new_documento['id']}), 201
    except Exception as e:
        print(f"Error saving document to Supabase: {e}")
        return jsonify({'error': f'Error saving document: {str(e)}'}), 500

@app.route('/api/documentacion', methods=['GET'])
@login_required # Protected
def get_documentacion():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
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
        print(f"Error fetching documentation from Supabase: {e}")
        return jsonify({'error': f'Error fetching documentation: {str(e)}'}), 500

@app.route('/api/documentacion/dias_con_documentos/<int:year>/<int:month>', methods=['GET'])
@login_required # Protected
def get_dias_con_documentos(year, month):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    month_str = str(month).zfill(2)
    search_pattern = f"{year}-{month_str}-"

    try:
        response = supabase.from_('documentacion').select('fecha').ilike('fecha', f'{search_pattern}%').execute()
        fechas = sorted(list(set([row['fecha'] for row in response.data])))
        return jsonify(fechas)
    except Exception as e:
        print(f"Error fetching days with documents from Supabase: {e}")
        return jsonify({'error': f'Error fetching days with documents: {str(e)}'}), 500

@app.route('/api/documentacion/<uuid:documento_id>', methods=['DELETE'])
@login_required # Protected
def delete_documento(documento_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        delete_response = supabase.from_('documentacion').delete().eq('id', str(documento_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Document not found.'}), 404
        return jsonify({'message': 'Document deleted successfully.'}), 200
    except Exception as e:
        print(f"Error deleting document from Supabase: {e}")
        return jsonify({'error': f'Error deleting document: {str(e)}'}), 500

@app.route('/api/tipos_documento', methods=['GET'])
@login_required # Protected
def get_tipos_documento():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
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
        print(f"Error fetching document types from Supabase: {e}")
        return jsonify({'error': f'Error fetching document types: {str(e)}'}), 500

# --- API Routes for Routines (Adapted for Supabase) ---

@app.route('/api/rutinas', methods=['POST'])
def add_rutina():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    data = request.json
    nombre = data.get('nombre')
    hora = data.get('hora')
    dias = data.get('dias')

    if not nombre or not dias:
        return jsonify({'error': 'Routine name and days of the week are mandatory.'}), 400
    
    if not isinstance(dias, list) or not all(isinstance(d, int) and 0 <= d <= 6 for d in dias):
        return jsonify({'error': 'Days must be a list of integers between 0 and 6.'}), 400

    if hora:
        try:
            datetime.strptime(hora, '%H:%M')
        except ValueError:
            return jsonify({'error': 'Invalid time format. Use HH:MM'}), 400

    hora_para_db = hora if hora else None

    try:
        dias_semana_json = json.dumps(dias)
        insert_data = {'nombre': nombre, 'hora': hora_para_db, 'dias_semana': dias_semana_json}
        response = supabase.from_('rutina').insert(insert_data).execute()
        new_rutina = response.data[0]

        return jsonify({'id': new_rutina['id'], 'nombre': new_rutina['nombre'], 'hora': new_rutina['hora'], 'dias': dias}), 201
    except Exception as e:
        print(f"Error adding routine to Supabase: {e}")
        return jsonify({'error': f'Error adding routine: {str(e)}'}), 500

@app.route('/api/rutinas', methods=['GET'])
def get_rutinas():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        response = supabase.from_('rutina').select('id,nombre,hora,dias_semana').order('id', desc=True).execute()
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
                    print(f"Warning: Could not decode or incorrect type for dias_semana of routine {rutina['id']}. Value: {raw_dias_semana}")

            rutinas_list.append({
                'id': rutina['id'],
                'nombre': rutina['nombre'],
                'hora': rutina['hora'],
                'dias': dias_semana_list
            })
        return jsonify(rutinas_list)
    except Exception as e:
        print(f"Error fetching routines from Supabase: {e}")
        return jsonify({'error': f'Error fetching routines: {str(e)}'}), 500

@app.route('/api/rutinas/<uuid:rutina_id>', methods=['DELETE'])
def delete_rutina(rutina_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        delete_response = supabase.from_('rutina').delete().eq('id', str(rutina_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Routine not found.'}), 404
        return jsonify({'message': 'Routine deleted successfully.'}), 200
    except Exception as e:
        print(f"Error deleting routine from Supabase: {e}")
        return jsonify({'error': f'Error deleting routine: {str(e)}'}), 500

@app.route('/api/rutinas/completadas_por_dia/<string:fecha>', methods=['GET'])
def get_rutinas_completadas_por_dia(fecha):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        response = supabase.from_('rutina_completada_dia').select('rutina_id').eq('fecha_completado', fecha).execute()
        completed_routine_ids = [item['rutina_id'] for item in response.data]
        return jsonify(completed_routine_ids), 200
    except Exception as e:
        print(f"Error fetching completed routines by day: {e}")
        return jsonify({'error': f'Error fetching completed routines: {str(e)}'}), 500

@app.route('/api/rutinas/<uuid:rutina_id>/toggle_completada_dia', methods=['POST'])
def toggle_rutina_completada_dia(rutina_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    data = request.json
    fecha = data.get('fecha')

    if not fecha:
        return jsonify({'error': 'Date is mandatory to update routine status.'}), 400

    try:
        response = supabase.from_('rutina_completada_dia').select('id').eq('rutina_id', str(rutina_id)).eq('fecha_completado', fecha).execute()
        
        if response.data:
            delete_response = supabase.from_('rutina_completada_dia').delete().eq('rutina_id', str(rutina_id)).eq('fecha_completado', fecha).execute()
            if not delete_response.data:
                raise Exception("Could not uncomplete the routine.")
            return jsonify({'message': 'Routine marked as incomplete for the day.'}), 200
        else:
            insert_data = {'rutina_id': str(rutina_id), 'fecha_completado': fecha}
            insert_response = supabase.from_('rutina_completada_dia').insert(insert_data).execute()
            if not insert_response.data:
                raise Exception("Could not complete the routine.")
            return jsonify({'message': 'Routine marked as completed for the day.'}), 201
    except Exception as e:
        print(f"Error changing routine status by day: {e}")
        return jsonify({'error': f'Error updating routine status: {str(e)}'}), 500

# --- API Routes for Shopping List (Adapted for Supabase) ---

@app.route('/api/lista_compra', methods=['GET'])
def get_lista_compra():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        response = supabase.from_('lista_compra').select('id,item,comprado').order('id', desc=True).execute()
        items = response.data
        return jsonify([
            {
                'id': item['id'],
                'item': item['item'],
                'comprado': item['comprado']
            } for item in items
        ])
    except Exception as e:
        print(f"Error fetching shopping list from Supabase: {e}")
        return jsonify({'error': f'Error fetching shopping list: {str(e)}'}), 500

@app.route('/api/lista_compra', methods=['POST'])
def add_item_lista_compra():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    data = request.json
    item_text = data.get('item')

    if not item_text:
        return jsonify({'error': 'Item text is mandatory.'}), 400

    try:
        insert_data = {'item': item_text, 'comprado': False}
        response = supabase.from_('lista_compra').insert(insert_data).execute()
        new_item = response.data[0]

        return jsonify({'id': new_item['id'], 'item': new_item['item'], 'comprado': new_item['comprado']}), 201
    except Exception as e:
        print(f"Error adding item to shopping list in Supabase: {e}")
        return jsonify({'error': f'Error adding item: {str(e)}'}), 500

@app.route('/api/lista_compra/<uuid:item_id>/toggle_comprado', methods=['PATCH'])
def toggle_item_comprado(item_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        response = supabase.from_('lista_compra').select('comprado').eq('id', str(item_id)).limit(1).execute()
        item = response.data[0] if response.data else None

        if not item:
            return jsonify({'error': 'Item not found.'}), 404

        new_state = not item['comprado']
        update_response = supabase.from_('lista_compra').update({'comprado': new_state}).eq('id', str(item_id)).execute() 
        
        if not update_response.data:
            return jsonify({'error': 'Item not found or could not be updated.'}), 404

        return jsonify({'id': str(item_id), 'comprado': new_state}), 200
    except Exception as e:
        print(f"Error changing item status in Supabase: {e}")
        return jsonify({'error': f'Error changing item status: {str(e)}'}), 500

@app.route('/api/lista_compra/<uuid:item_id>', methods=['DELETE'])
def delete_item_lista_compra(item_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        delete_response = supabase.from_('lista_compra').delete().eq('id', str(item_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Item not found.'}), 404
        return jsonify({'message': 'Item deleted successfully.'}), 200
    except Exception as e:
        print(f"Error deleting item from shopping list in Supabase: {e}")
        return jsonify({'error': f'Error deleting item: {str(e)}'}), 500

@app.route('/api/lista_compra/clear_all', methods=['DELETE'])
def clear_all_shopping_list_items():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        # The way to clear the entire table in Supabase without WHERE
        delete_response = supabase.from_('lista_compra').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        
        if delete_response.data is None: 
             return jsonify({'message': 'Shopping list cleared successfully.'}), 200
        else: 
             return jsonify({'message': 'Shopping list cleared successfully.', 'details': delete_response.data}), 200

    except Exception as e:
        print(f"Database error clearing all shopping list items in Supabase: {e.args[0]}")
        return jsonify({'error': f"Database error: {e.args[0]}"}), 500
# --- NEW API Routes for Quick Notes ---
@app.route('/api/notas', methods=['POST'])
def add_nota_rapida():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    data = request.json
    texto = data.get('texto')
    fecha = data.get('fecha')

    if not texto:
        return jsonify({'error': 'Note text is mandatory.'}), 400
    
    if not fecha:
        fecha = datetime.now().strftime('%Y-%m-%d')

    try:
        insert_data = {'texto': texto, 'fecha': fecha}
        response = supabase.from_('nota_rapida').insert(insert_data).execute()
        new_note = response.data[0]
        return jsonify({'id': new_note['id'], 'texto': new_note['texto'], 'fecha': new_note['fecha']}), 201
    except Exception as e:
        print(f"Error adding quick note to Supabase: {e}")
        return jsonify({'error': f'Error adding note: {str(e)}'}), 500

@app.route('/api/notas', methods=['GET'])
def get_notas_rapidas():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
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
        print(f"Error fetching quick notes from Supabase: {e}")
        return jsonify({'error': f'Error fetching notes: {str(e)}'}), 500

@app.route('/api/notas/<uuid:note_id>', methods=['DELETE'])
def delete_nota_rapida(note_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        delete_response = supabase.from_('nota_rapida').delete().eq('id', str(note_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Note not found.'}), 404
        return jsonify({'message': 'Note deleted successfully.'}), 200
    except Exception as e:
        print(f"Error deleting quick note from Supabase: {e}")
        return jsonify({'error': f'Error deleting note: {str(e)}'}), 500

# --- NEW API Routes for Citas ---
@app.route('/api/citas', methods=['POST'])
def add_cita():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    data = request.json
    nombre = data.get('nombre')
    fecha = data.get('fecha')
    hora = data.get('hora')
    # NEW: Get requirements list (already JSON string from frontend)
    recordatorio = data.get('recordatorio') 

    if not nombre or not fecha:
        return jsonify({'error': 'Appointment name and date are mandatory.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
        if hora:
            datetime.strptime(hora, '%H:%M')
    except ValueError:
        return jsonify({'error': 'Invalid date or time format. Use (YYYY-MM-DD) and HH:MM'}), 400
    
    hora_para_db = hora if hora else None

    try:
        insert_data = {'nombre': nombre, 'fecha': fecha, 'hora': hora_para_db, 'completada': False, 'recordatorio': recordatorio}
        response = supabase.from_('cita').insert(insert_data).execute()
        new_cita = response.data[0]
        return jsonify({'id': new_cita['id'], 'nombre': new_cita['nombre'], 'fecha': new_cita['fecha'], 'hora': new_cita['hora'], 'completada': new_cita['completada'], 'recordatorio': new_cita.get('recordatorio')}), 201
    except Exception as e:
        print(f"Error adding appointment to Supabase: {e}")
        return jsonify({'error': f'Error adding appointment: {str(e)}'}), 500

@app.route('/api/citas/all', methods=['GET'])
def get_all_citas():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        # Include 'recordatorio' in the select statement
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada,recordatorio').order('fecha').order('hora').execute()
        citas = response.data
        return jsonify([
            {
                'id': cita['id'],
                'nombre': cita['nombre'],
                'fecha': cita['fecha'],
                'hora': cita['hora'],
                'completada': cita['completada'],
                'recordatorio': cita.get('recordatorio') # Include recordatorio
            } for cita in citas
        ])
    except Exception as e:
        print(f"Error fetching all appointments from Supabase: {e}")
        return jsonify({'error': f'Error fetching appointments: {str(e)}'}), 500

@app.route('/api/citas/<string:fecha>', methods=['GET'])
def get_citas_by_date(fecha):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use (YYYY-MM-DD)'}), 400

    try:
        # Include 'recordatorio' in the select statement
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada,recordatorio').eq('fecha', fecha).order('hora').execute()
        citas = response.data
        return jsonify([
            {
                'id': cita['id'],
                'nombre': cita['nombre'],
                'fecha': cita['fecha'],
                'hora': cita['hora'],
                'completada': cita['completada'],
                'recordatorio': cita.get('recordatorio') # Include recordatorio
            } for cita in citas
        ])
    except Exception as e:
        print(f"Error fetching appointments by date from Supabase: {e}")
        return jsonify({'error': f'Error fetching appointments by date: {str(e)}'}), 500

@app.route('/api/citas/<int:year>/<int:month>', methods=['GET'])
def get_citas_for_month(year, month):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    
    # Calculate the first and last day of the month
    start_date = date(year, month, 1)
    end_date = date(year, month, calendar.monthrange(year, month)[1]) # Get the last day of the month

    try:
        # Filter appointments within the month range
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
                'recordatorio': cita.get('recordatorio') # Include recordatorio
            })
        return jsonify(processed_citas)
    except Exception as e:
        print(f"Error fetching appointments for the month from Supabase: {e}")
        return jsonify({'error': f'Error fetching appointments for the month: {str(e)}'}), 500

@app.route('/api/citas/proximas/<int:year>/<int:month>', methods=['GET'])
def get_proximas_citas(year, month):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    
    today = datetime.now().date()
    # Get all appointments from the current date onwards, ordered by date and time
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
                'recordatorio': cita.get('recordatorio') # Include recordatorio
            })
        return jsonify(processed_citas)
    except Exception as e:
        print(f"Error fetching upcoming appointments from Supabase: {e}")
        return jsonify({'error': f'Error fetching upcoming appointments: {str(e)}'}), 500


@app.route('/api/citas/<uuid:cita_id>', methods=['GET'])
def get_cita_by_id(cita_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        # Include 'recordatorio' in the select statement
        response = supabase.from_('cita').select('id,nombre,fecha,hora,completada,recordatorio').eq('id', str(cita_id)).limit(1).execute()
        cita = response.data[0] if response.data else None
        if not cita:
            return jsonify({'error': 'Appointment not found.'}), 404
        return jsonify({
            'id': cita['id'],
            'nombre': cita['nombre'],
            'fecha': cita['fecha'],
            'hora': cita['hora'],
            'completada': cita['completada'],
            'recordatorio': cita.get('recordatorio') # Include recordatorio
        }), 200
    except Exception as e:
        print(f"Error fetching appointment by ID from Supabase: {e}")
        return jsonify({'error': f'Error fetching appointment: {str(e)}'}), 500

@app.route('/api/citas/<uuid:cita_id>', methods=['PUT'])
def update_cita(cita_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    data = request.json
    nombre = data.get('nombre')
    fecha = data.get('fecha')
    hora = data.get('hora')
    # NEW: Get requirements list (already JSON string from frontend)
    recordatorio = data.get('recordatorio')

    if not nombre or not fecha:
        return jsonify({'error': 'Appointment name and date are mandatory.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
        if hora:
            datetime.strptime(hora, '%H:%M')
    except ValueError:
        return jsonify({'error': 'Invalid date or time format. Use (YYYY-MM-DD) and HH:MM'}), 400
    
    hora_para_db = hora if hora else None

    try:
        update_data = {'nombre': nombre, 'fecha': fecha, 'hora': hora_para_db, 'recordatorio': recordatorio}
        update_response = supabase.from_('cita').update(update_data).eq('id', str(cita_id)).execute()
        
        if not update_response.data:
            return jsonify({'error': 'Appointment not found for update.'}), 404
        return jsonify({'message': 'Appointment updated successfully.', 'id': str(cita_id)}), 200
    except Exception as e:
        print(f"Error updating appointment in Supabase: {e}")
        return jsonify({'error': f'Error updating appointment: {str(e)}'}), 500

@app.route('/api/citas/<uuid:cita_id>/toggle_completada', methods=['PATCH'])
def toggle_cita_completada(cita_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        response = supabase.from_('cita').select('completada').eq('id', str(cita_id)).limit(1).execute()
        cita = response.data[0] if response.data else None

        if not cita:
            return jsonify({'error': 'Appointment not found.'}), 404

        new_state = not cita['completada']
        
        update_response = supabase.from_('cita').update({'completada': new_state}).eq('id', str(cita_id)).execute()
        
        if not update_response.data:
            return jsonify({'error': 'Appointment not found or could not be updated.'}), 404

        return jsonify({'id': str(cita_id), 'completada': new_state}), 200
    except Exception as e:
        print(f"Error changing appointment status in Supabase: {e}")
        return jsonify({'error': f'Error updating appointment: {str(e)}'}), 500

# NEW ROUTE: Toggle individual requirement's checked status
@app.route('/api/citas/<uuid:cita_id>/toggle_requisito_completado', methods=['PATCH'])
def toggle_requisito_completado(cita_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    data = request.json
    requisito_index = data.get('index')

    if not isinstance(requisito_index, int):
        return jsonify({'error': 'Requirement index is mandatory and must be an integer.'}), 400

    try:
        # Fetch the current appointment to get its recordatorio
        response = supabase.from_('cita').select('recordatorio').eq('id', str(cita_id)).limit(1).execute()
        cita = response.data[0] if response.data else None

        if not cita:
            return jsonify({'error': 'Appointment not found.'}), 404

        current_recordatorio_json_str = cita.get('recordatorio')
        
        requisitos = []
        if current_recordatorio_json_str:
            try:
                requisitos = json.loads(current_recordatorio_json_str)
            except json.JSONDecodeError:
                print(f"Error decoding recordatorio JSON for cita {cita_id}: {current_recordatorio_json_str}")
                return jsonify({'error': 'Invalid recordatorio format.'}), 400

        if not (0 <= requisito_index < len(requisitos)):
            return jsonify({'error': 'Invalid requirement index.'}), 400

        # Toggle the 'checked' status for the specified requirement
        requisitos[requisito_index]['checked'] = not requisitos[requisito_index]['checked']

        # Convert back to JSON string to store in Supabase
        updated_recordatorio_json_str = json.dumps(requisitos)

        # Update the appointment with the new recordatorio
        update_response = supabase.from_('cita').update({'recordatorio': updated_recordatorio_json_str}).eq('id', str(cita_id)).execute()
        
        if not update_response.data:
            return jsonify({'error': 'Appointment not found or could not update requirement.'}), 404

        return jsonify({'message': 'Requirement status updated successfully.', 'id': str(cita_id), 'index': requisito_index, 'new_state': requisitos[requisito_index]['checked']}), 200
    except Exception as e:
        print(f"Error toggling requirement status in Supabase: {e}")
        return jsonify({'error': f'Error updating requirement: {str(e)}'}), 500


@app.route('/api/citas/<uuid:cita_id>', methods=['DELETE'])
def delete_cita(cita_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        delete_response = supabase.from_('cita').delete().eq('id', str(cita_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Appointment not found.'}), 404
        return jsonify({'message': 'Appointment deleted successfully.'}), 200
    except Exception as e:
        print(f"Error deleting appointment from Supabase: {e}")
        return jsonify({'error': f'Error deleting appointment: {str(e)}'}), 500

# --- NEW API for Supermarkets ---
@app.route('/api/supermarkets', methods=['POST'])
def add_supermarket():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    data = request.get_json()
    name = data.get('name')

    if not name:
        return jsonify({'error': 'Supermarket name is mandatory.'}), 400
    
    try:
        # Attempt to insert the new supermarket
        response = supabase.from_('supermarkets').insert({"name": name}).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        # Catch duplication errors (e.g., UNIQUE constraint)
        if "duplicate key value violates unique constraint" in str(e):
            return jsonify({'error': 'A supermarket with that name already exists.'}), 409 # Conflict
        print(f"Error adding supermarket to Supabase: {e}")
        return jsonify({'error': f'Error adding supermarket: {str(e)}'}), 500

@app.route('/api/supermarkets', methods=['GET'])
def get_supermarkets():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        response = supabase.from_('supermarkets').select("*").order('name').execute()
        return jsonify(response.data), 200
    except Exception as e:
        print(f"Error fetching supermarkets from Supabase: {e}")
        return jsonify({'error': f'Error fetching supermarkets: {str(e)}'}), 500

@app.route('/api/supermarkets/<uuid:supermarket_id>', methods=['DELETE'])
def delete_supermarket(supermarket_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        delete_response = supabase.from_('supermarkets').delete().eq('id', str(supermarket_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Supermarket not found.'}), 404
        return jsonify({'message': 'Supermarket deleted successfully.'}), 200
    except Exception as e:
        print(f"Error deleting supermarket from Supabase: {e}")
        return jsonify({'error': f'Error deleting supermarket: {str(e)}'}), 500


# --- API for Food (Modified to use supermarket_id) ---
@app.route('/api/ingredients', methods=['POST'])
def add_ingredient():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    data = request.get_json()
    name = data.get('name')
    # Changed to 'supermarket_id' that the frontend will send (or the name if it's a string)
    supermarket_value = data.get('supermarket') # This will be the supermarket NAME
    price_per_unit = data.get('price_per_unit')
    calories_per_100g = data.get('calories_per_100g')
    proteins_per_100g = data.get('proteins_per_100g')
    carbs_per_100g = data.get('carbs_per_100g')
    fats_per_100g = data.get('fats_per_100g')

    if not all([name, price_per_unit is not None, calories_per_100g is not None, proteins_per_100g is not None, carbs_per_100g is not None, fats_per_100g is not None]):
        return jsonify({'error': 'Missing mandatory ingredient data.'}), 400

    supermarket_id = None
    if supermarket_value:
        try:
            # Search for the supermarket ID by its name
            supermarket_response = supabase.from_('supermarkets').select('id').eq('name', supermarket_value).single().execute()
            supermarket_id = supermarket_response.data['id']
        except Exception as e:
            print(f"Warning: Supermarket '{supermarket_value}' not found or error searching for it: {e}")
            # You can choose to return an error or simply not assign a supermarket_id
            # For this case, we will continue without assigning the ID if not found.
            supermarket_id = None


    try:
        insert_data = {
            'name': name,
            'supermarket_id': supermarket_id, # Use the supermarket ID
            'price_per_unit': price_per_unit,
            'calories_per_100g': calories_per_100g,
            'proteins_per_100g': proteins_per_100g,
            'carbs_per_100g': carbs_per_100g,
            'fats_per_100g': fats_per_100g
        }
        response = supabase.from_('ingredients').insert(insert_data).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        print(f"Error adding ingredient to Supabase: {e}")
        return jsonify({'error': f'Error adding ingredient: {str(e)}'}), 500

@app.route('/api/ingredients', methods=['GET'])
def get_ingredients():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        # Perform an implicit JOIN to get the supermarket name
        response = supabase.from_('ingredients').select('*, supermarkets(name)').order('name').execute()
        
        # Map the results to include the supermarket name directly
        ingredients_with_supermarket_names = []
        for ingredient in response.data:
            supermarket_name = ingredient['supermarkets']['name'] if ingredient['supermarkets'] else None
            ingredients_with_supermarket_names.append({
                'id': ingredient['id'],
                'name': ingredient['name'],
                'supermarket': supermarket_name, # Here we use the name for the frontend
                'price_per_unit': ingredient['price_per_unit'],
                'calories_per_100g': ingredient['calories_per_100g'],
                'proteins_per_100g': ingredient['proteins_per_100g'],
                'carbs_per_100g': ingredient['carbs_per_100g'],
                'fats_per_100g': ingredient['fats_per_100g']
            })
        return jsonify(ingredients_with_supermarket_names), 200
    except Exception as e:
        print(f"Error fetching ingredients from Supabase: {e}")
        return jsonify({'error': f'Error fetching ingredients: {str(e)}'}), 500

@app.route('/api/ingredients/<uuid:ingredient_id>', methods=['DELETE'])
def delete_ingredient(ingredient_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        delete_response = supabase.from_('ingredients').delete().eq('id', str(ingredient_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Ingredient not found.'}), 404
        return jsonify({'message': 'Ingredient deleted successfully.'}), 200
    except Exception as e:
        print(f"Error deleting ingredient from Supabase: {e}")
        return jsonify({'error': f'Error deleting ingredient: {str(e)}'}), 500

@app.route('/api/recipes', methods=['POST'])
def add_recipe():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    data = request.get_json()
    name = data.get('name')
    ingredients_list = data.get('ingredients') 
    total_cost = data.get('total_cost')
    total_calories = data.get('total_calories')
    total_proteins = data.get('total_proteins')
    total_carbs = data.get('total_carbs')
    total_fats = data.get('fats') # Fixed: Should be 'fats' as per request JSON, not 'total_fats'
    description = data.get('description') # NEW: get description


    if not all([name, ingredients_list is not None, total_cost is not None, total_calories is not None,
                total_proteins is not None, total_carbs is not None, total_fats is not None]):
        return jsonify({'error': 'Missing mandatory recipe data.'}), 400
    
    try:
        insert_data = {
            'name': name,
            'description': description, # NEW: add description
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
            return jsonify({'error': 'Could not insert recipe.'}), 500
    except Exception as e:
        print(f"Error adding recipe to Supabase: {e}")
        return jsonify({'error': f'Error adding recipe: {str(e)}'}), 500

@app.route('/api/recipes', methods=['GET'])
def get_recipes():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        response = supabase.from_('recipes').select('*').order('name').execute()
        recipes = response.data if response and response.data else []
        return jsonify(recipes), 200
    except Exception as e:
        print(f"Error fetching recipes from Supabase: {e}")
        return jsonify({'error': f'Error fetching recipes: {str(e)}'}), 500

@app.route('/api/recipes/<uuid:recipe_id>', methods=['DELETE'])
def delete_recipe(recipe_id):
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    try:
        delete_response = supabase.from_('recipes').delete().eq('id', str(recipe_id)).execute()
        if not delete_response.data:
            return jsonify({'error': 'Recipe not found.'}), 404
        return jsonify({'message': 'Recipe deleted successfully.'}), 200
    except Exception as e:
        print(f"Error deleting recipe from Supabase: {e}")
        return jsonify({'error': f'Error deleting recipe: {str(e)}'}), 500

@app.route('/api/weekly_menu', methods=['GET'])
def get_weekly_menu():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    # Get the unique weekly menu
    # Constant for the weekly menu ID (for a single user)
    WEEKLY_MENU_SINGLETON_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11" 
    try:
        response = supabase.from_('weekly_menu').select('menu').eq('id', WEEKLY_MENU_SINGLETON_ID).single().execute()
        menu_data = response.data['menu'] if response and response.data else {}
        return jsonify(menu_data), 200
    except Exception as e:
        # If it does not exist, Supabase may return an error. We treat it as an empty menu.
        print(f"Error fetching weekly menu from Supabase (may not exist): {e}")
        return jsonify({}), 200 # Return empty dictionary if not found or error

@app.route('/api/weekly_menu', methods=['PUT'])
def save_weekly_menu():
    if supabase is None:
        return jsonify({'error': 'Database service unavailable.'}), 503
    data = request.get_json()
    menu_data = data.get('menu') # This will be the weekly menu dictionary

    if menu_data is None:
        return jsonify({'error': 'Menu data is mandatory.'}), 400
    # Constant for the weekly menu ID (for a single user)
    WEEKLY_MENU_SINGLETON_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11" 
    try:
        # Use upsert to insert if it doesn't exist, or update if the record with the fixed ID exists.
        insert_data = {
            'id': WEEKLY_MENU_SINGLETON_ID,
            'menu': menu_data # Supabase stores JSONB, so it can handle the dictionary directly
        }
        # Make sure 'id' is the primary key or has a unique constraint for upsert to work.
        response = supabase.from_('weekly_menu').upsert(insert_data, on_conflict='id').execute()
        
        if response and response.data:
            return jsonify({'message': 'Weekly menu saved successfully.', 'menu': response.data[0]}), 200
        else:
            return jsonify({'error': 'Could not save weekly menu.'}), 500
    except Exception as e:
        print(f"Error saving weekly menu to Supabase: {e}")
        return jsonify({'error': f'Error saving weekly menu: {str(e)}'}), 500

# Punto de entrada de la aplicación
if __name__ == '__main__':
    # Es crucial que estas funciones se ejecuten al inicio para la lógica diaria
    init_db_supabase()
    generate_tasks_for_today_from_routines()
    manage_overdue_tasks()
    
    # Puerto para la aplicación Flask (Render usará el puerto 10000 por defecto)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
