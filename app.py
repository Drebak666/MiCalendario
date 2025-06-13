import sqlite3
from flask import Flask, render_template, request, jsonify, g
from datetime import datetime, date
import os

app = Flask(__name__) # CORREGIDO: __name__ en lugar de __app__
DATABASE = 'agenda.db'

# Función para obtener la conexión a la base de datos
# Utiliza 'g' para almacenar la conexión durante la vida de la solicitud
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row # Para poder acceder a las columnas por nombre (ej. tarea['id'])
    return db

# Cerrar la conexión a la base de datos al finalizar cada solicitud
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close() # Cierra la conexión a la base de datos

# Función para inicializar la base de datos (crear las tablas si no existen)
def init_db():
    with app.app_context(): # 'app.app_context()' es necesario para usar 'g' fuera de una solicitud
        db = get_db()
        cursor = db.cursor()
        
        # Tabla para tareas diarias
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tarea (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                texto TEXT NOT NULL,
                completada INTEGER DEFAULT 0,
                hora TEXT DEFAULT NULL  -- Columna para la hora, opcional
            )
        ''')
        
        # --- NUEVA TABLA: Para registros importantes/de salud ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS registro_importante (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,        -- Fecha del evento/cita
                titulo TEXT NOT NULL,       -- Título corto o resumen
                descripcion TEXT,           -- Descripción detallada (opcional)
                tipo TEXT                   -- Tipo de registro (ej. 'salud', 'cita', 'evento', 'documento', etc.)
            )
        ''')
        
        db.commit() # Guardar los cambios (creación de tablas)
    print("Base de datos SQLite inicializada o ya existente.")
    
    # Llamar a la función de gestión de tareas vencidas aquí
    manage_overdue_tasks()

# Función para gestionar tareas vencidas (las mueve o elimina)
def manage_overdue_tasks():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        print(f"[{datetime.now()}] Iniciando gestión de tareas vencidas para el día: {today_str}")

        # 1. Eliminar tareas COMPLETADAS de días ANTERIORES al actual
        cursor.execute("DELETE FROM tarea WHERE fecha < ? AND completada = 1", (today_str,))
        deleted_count = cursor.rowcount
        print(f"[{datetime.now()}] Eliminadas {deleted_count} tareas completadas de días anteriores.")

        # 2. Mover tareas INCOMPLETAS de días ANTERIORES al día actual
        cursor.execute("UPDATE tarea SET fecha = ? WHERE fecha < ? AND completada = 0", (today_str, today_str))
        moved_count = cursor.rowcount
        print(f"[{datetime.now()}] Movidas {moved_count} tareas incompletas de días anteriores al día actual.")

        db.commit() # Guardar los cambios en la base de datos
        print(f"[{datetime.now()}] Gestión de tareas vencidas finalizada.")


# --- Rutas de la Aplicación ---

# Ruta principal que sirve el HTML de la agenda (index.html)
@app.route('/')
def index():
    return render_template('index.html')

# Ruta para el calendario
@app.route('/calendario')
def calendario():
    return render_template('calendario.html')

# Ruta para la página de registro de citas importantes
@app.route('/registro')
def registro():
    return render_template('registro.html')

# --- Rutas API para Tareas ---

# API para obtener tareas para una fecha específica
@app.route('/api/tareas/<string:fecha>', methods=['GET'])
def get_tareas_by_date(fecha):
    db = get_db()
    cursor = db.cursor()
    try:
        datetime.strptime(fecha, '%Y-%m-%d') # Validar formato de fecha
    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido. Usa YYYY-MM-DD'}), 400

    # Seleccionar tareas para la fecha y ordenar por hora
    cursor.execute("SELECT id, texto, completada, hora, fecha FROM tarea WHERE fecha = ? ORDER BY hora ASC", (fecha,))
    tareas = cursor.fetchall()
    
    # Convertir las filas a diccionarios para la respuesta JSON
    tareas_list = []
    for tarea in tareas:
        tareas_list.append({
            'id': tarea['id'],
            'fecha': tarea['fecha'], 
            'texto': tarea['texto'],
            'completada': bool(tarea['completada']), 
            'hora': tarea['hora']
        })
    return jsonify(tareas_list)

# API para obtener días con tareas para un mes y año específicos (para el calendario)
@app.route('/api/tareas/dias_con_tareas/<int:year>/<int:month>', methods=['GET'])
def get_dias_con_tareas(year, month):
    db = get_db()
    cursor = db.cursor()
    month_str = str(month).zfill(2) # Asegura formato '01', '02', etc.

    # Consulta para obtener fechas distintas con tareas en el mes y año dados
    # REVISADO: Usar parámetro para prevenir inyección SQL
    search_pattern = f"{year}-{month_str}-%"
    cursor.execute("SELECT DISTINCT fecha FROM tarea WHERE fecha LIKE ?", (search_pattern,))
    dias = [row[0] for row in cursor.fetchall()] # Extraer solo la fecha de cada tupla
    return jsonify(dias)

# API para añadir una nueva tarea
@app.route('/api/tareas', methods=['POST'])
def add_tarea():
    db = get_db()
    cursor = db.cursor()
    data = request.json # Obtener los datos JSON del request
    fecha = data.get('fecha')
    texto = data.get('texto')
    hora = data.get('hora') # Obtener la hora (puede ser None)

    if not fecha or not texto:
        return jsonify({'error': 'Fecha y texto de tarea son obligatorios.'}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d') # Validar formato de fecha
        if hora:
            datetime.strptime(hora, '%H:%M') # Validar formato de hora si está presente
    except ValueError:
        return jsonify({'error': 'Formato de fecha u hora inválido. Usa YYYY-MM-DD y HH:MM'}), 400

    # Insertar la nueva tarea en la tabla
    cursor.execute("INSERT INTO tarea (fecha, texto, completada, hora) VALUES (?, ?, ?, ?)", (fecha, texto, 0, hora))
    db.commit() # Guardar los cambios en la base de datos
    new_id = cursor.lastrowid # Obtener el ID de la tarea recién insertada

    # Devolver los detalles de la nueva tarea en formato JSON
    return jsonify({'id': new_id, 'fecha': fecha, 'texto': texto, 'completada': False, 'hora': hora}), 201

# API para cambiar el estado de completada de una tarea
@app.route('/api/tareas/<int:tarea_id>/toggle_completada', methods=['PATCH'])
def toggle_tarea_completada(tarea_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT completada FROM tarea WHERE id = ?", (tarea_id,))
    tarea = cursor.fetchone()

    if not tarea:
        return jsonify({'error': 'Tarea no encontrada.'}), 404

    new_state = 1 if not bool(tarea['completada']) else 0 # Invertir el estado (0 a 1, 1 a 0)
    cursor.execute("UPDATE tarea SET completada = ? WHERE id = ?", (new_state, tarea_id))
    db.commit() # Guardar los cambios
    return jsonify({'id': tarea_id, 'completada': bool(new_state)}), 200

# API para eliminar una tarea
@app.route('/api/tareas/<int:tarea_id>', methods=['DELETE'])
def delete_tarea(tarea_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM tarea WHERE id = ?", (tarea_id,))
    db.commit() # Guardar los cambios
    if cursor.rowcount == 0: # Si no se eliminó ninguna fila, la tarea no existía
        return jsonify({'error': 'Tarea no encontrada.'}), 404
    return jsonify({'message': 'Tarea eliminada exitosamente.'}), 200


# --- NUEVAS RUTAS API para Registros Importantes ---

# API para guardar un registro importante (por ejemplo, desde una tarea existente o desde el modal directo)
@app.route('/api/registros_importantes/add_from_task', methods=['POST'])
def add_registro_from_task():
    db = get_db()
    cursor = db.cursor()
    data = request.json
    
    fecha = data.get('fecha')
    titulo = data.get('titulo')
    descripcion = data.get('descripcion')
    tipo = data.get('tipo')
    
    if not fecha or not titulo:
        return jsonify({'error': 'Fecha y título son obligatorios para el registro importante.'}), 400

    # Validar formato de fecha (YYYY-MM-DD)
    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except (ValueError, TypeError): # Añadido TypeError por si 'fecha' no es string
        return jsonify({'error': 'Formato de fecha inválido. Usa YYYY-MM-DD'}), 400

    try:
        cursor.execute("INSERT INTO registro_importante (fecha, titulo, descripcion, tipo) VALUES (?, ?, ?, ?)",
                       (fecha, titulo, descripcion, tipo))
        db.commit()
        new_id = cursor.lastrowid
        return jsonify({'message': 'Registro importante guardado', 'id': new_id}), 201
    except sqlite3.Error as e:
        print(f"Error de base de datos al guardar registro importante: {e}")
        return jsonify({'error': f'Error de base de datos al guardar: {str(e)}'}), 500

# API para obtener todos los registros importantes
@app.route('/api/registros_importantes', methods=['GET'])
def get_registros_importantes():
    db = get_db()
    cursor = db.cursor()
    
    # Ordenar por fecha descendente (más recientes primero) y luego por ID descendente
    cursor.execute("SELECT id, fecha, titulo, descripcion, tipo FROM registro_importante ORDER BY fecha DESC, id DESC")
    registros = cursor.fetchall()
    
    registros_list = []
    for registro in registros:
        registros_list.append({
            'id': registro['id'],
            'fecha': registro['fecha'],
            'titulo': registro['titulo'],
            'descripcion': registro['descripcion'],
            'tipo': registro['tipo']
        })
    return jsonify(registros_list)

# API: Para obtener días con registros importantes para un mes y año específicos
@app.route('/api/registros_importantes/dias_con_registros/<int:year>/<int:month>', methods=['GET'])
def get_dias_con_registros(year, month):
    db = get_db()
    cursor = db.cursor()
    month_str = str(month).zfill(2)

    # REVISADO: Usar parámetro para prevenir inyección SQL
    search_pattern = f"{year}-{month_str}-%"
    cursor.execute("SELECT DISTINCT fecha FROM registro_importante WHERE fecha LIKE ?", (search_pattern,))
    dias = [row[0] for row in cursor.fetchall()]
    return jsonify(dias)


# API para eliminar un registro importante
@app.route('/api/registros_importantes/<int:registro_id>', methods=['DELETE'])
def delete_registro_importante(registro_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM registro_importante WHERE id = ?", (registro_id,))
    db.commit() # Guardar los cambios
    if cursor.rowcount == 0: # Si no se eliminó ninguna fila, el registro no existía
        return jsonify({'error': 'Registro importante no encontrado.'}), 404
    return jsonify({'message': 'Registro importante eliminado exitosamente.'}), 200


# Punto de entrada de la aplicación
if __name__ == '__main__':
    init_db() # Esto inicializa ambas tablas y gestiona las tareas vencidas
    # Obtener el puerto de las variables de entorno de Render (si existe), o usar 5000 para local
    port = int(os.environ.get("PORT", 5000))
    app.run(host='127.0.0.1', port=port, debug=True)