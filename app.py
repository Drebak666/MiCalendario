from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime
import os

# AÑADE ESTAS LÍNEAS AQUÍ ARRIBA:
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__) # 'app' debe definirse ANTES de usarla para SQLAlchemy o CORS
CORS(app) # CORS debe inicializarse con 'app'


# Configuración de la conexión a Supabase (usará DATABASE_URL de Render)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///tareas.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app) # Inicializamos SQLAlchemy DESPUÉS de definir 'app' y Flask-SQLAlchemy


# Define tu tabla 'tarea' para SQLAlchemy.
# ¡IMPORTANTE! He añadido la columna 'completada' que discutimos.
# Asegúrate de haber borrado la tabla 'tarea' en Supabase si ya existía para que se cree con esta nueva columna.
class Tarea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Text, nullable=False)
    texto = db.Column(db.Text, nullable=False)
    completada = db.Column(db.Boolean, default=False, nullable=False) # ¡NUEVA COLUMNA!

    def __repr__(self):
        return f'<Tarea {self.id}: {self.fecha} - {self.texto} (Completada: {self.completada})>'


def init_db():
    try:
        with app.app_context():
            db.create_all()
        print("Base de datos inicializada correctamente.")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

@app.route('/')
def index():
    # Eliminamos fecha_actual de aquí; se obtiene en JavaScript en index.html
    return render_template('index.html')

@app.route('/calendario')
def calendario():
    return render_template('calendario.html')

@app.route('/api/tareas', methods=['POST'])
def crear_tarea():
    data = request.get_json()
    print(f"Datos recibidos para crear_tarea: {data}")

    fecha = data.get('fecha')
    texto = data.get('texto')

    if not fecha or not texto:
        print("Error: Faltan datos (fecha o texto)")
        return jsonify({"error": "Faltan datos (fecha o texto)"}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        print(f"Error: Formato de fecha inválido para {fecha}. Se esperaba YYYY-MM-DD")
        return jsonify({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}), 400

    try:
        # Se añade la tarea con 'completada=False' por defecto gracias al modelo
        nueva_tarea = Tarea(fecha=fecha, texto=texto)
        db.session.add(nueva_tarea)
        db.session.commit()
        tarea_id = nueva_tarea.id
        print(f"Tarea '{texto}' guardada con ID: {tarea_id} para la fecha: {fecha}")
        # Asegúrate de devolver el estado 'completada' en la respuesta POST también
        return jsonify({"id": tarea_id, "fecha": fecha, "texto": texto, "completada": nueva_tarea.completada}), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error al insertar la tarea en la base de datos: {e}")
        return jsonify({"error": f"Error al guardar la tarea: {e}"}), 500

@app.route('/api/tareas/<fecha>', methods=['GET'])
def tareas_por_fecha(fecha):
    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}), 400

    # Cambiamos para obtener también el estado 'completada'
    tareas_db = Tarea.query.filter_by(fecha=fecha).all()
    tareas = [{"id": t.id, "texto": t.texto, "completada": t.completada} for t in tareas_db]
    return jsonify(tareas)

# ¡NUEVA RUTA API para marcar tareas como completadas/pendientes!
@app.route('/api/tareas/<int:tarea_id>/toggle_completada', methods=['PATCH'])
def toggle_completada(tarea_id):
    try:
        tarea = Tarea.query.get(tarea_id)
        if not tarea:
            return jsonify({"error": "Tarea no encontrada"}), 404

        tarea.completada = not tarea.completada # Invierte el estado actual
        db.session.commit()
        print(f"Tarea con ID {tarea_id} ahora completada: {tarea.completada}")
        return jsonify({"id": tarea.id, "completada": tarea.completada}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error al cambiar estado de la tarea: {e}")
        return jsonify({"error": f"Error al cambiar estado de la tarea: {e}"}), 500

@app.route('/api/tareas/<int:tarea_id>', methods=['DELETE'])
def borrar_tarea(tarea_id):
    try:
        tarea_a_borrar = Tarea.query.get(tarea_id)
        if tarea_a_borrar:
            db.session.delete(tarea_a_borrar)
            db.session.commit()
            print(f"Tarea con ID {tarea_id} eliminada.")
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": "Tarea no encontrada"}), 404
    except Exception as e:
        db.session.rollback()
        print(f"Error al borrar la tarea: {e}")
        return jsonify({"error": f"Error al borrar la tarea: {e}"}), 500

@app.route('/api/tareas-mes/<mes>', methods=['GET'])
def tareas_por_mes(mes):
    try:
        datetime.strptime(mes + '-01', '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Formato de mes inválido. Use YYYY-MM"}), 400

    fechas_distintas = db.session.query(Tarea.fecha).filter(Tarea.fecha.like(mes + '%')).distinct().all()
    fechas = [f[0] for f in fechas_distintas]
    return jsonify(fechas)

if __name__ == '__main__':
    init_db()
=======
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime
import os

# AÑADE ESTAS LÍNEAS AQUÍ ARRIBA:
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__) # 'app' debe definirse ANTES de usarla para SQLAlchemy o CORS
CORS(app) # CORS debe inicializarse con 'app'


# Configuración de la conexión a Supabase (usará DATABASE_URL de Render)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///tareas.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app) # Inicializamos SQLAlchemy DESPUÉS de definir 'app' y Flask-SQLAlchemy


# Define tu tabla 'tarea' para SQLAlchemy.
# ¡IMPORTANTE! He añadido la columna 'completada' que discutimos.
# Asegúrate de haber borrado la tabla 'tarea' en Supabase si ya existía para que se cree con esta nueva columna.
class Tarea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Text, nullable=False)
    texto = db.Column(db.Text, nullable=False)
    completada = db.Column(db.Boolean, default=False, nullable=False) # ¡NUEVA COLUMNA!

    def __repr__(self):
        return f'<Tarea {self.id}: {self.fecha} - {self.texto} (Completada: {self.completada})>'


def init_db():
    try:
        with app.app_context():
            db.create_all()
        print("Base de datos inicializada correctamente.")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

@app.route('/')
def index():
    # Eliminamos fecha_actual de aquí; se obtiene en JavaScript en index.html
    return render_template('index.html')

@app.route('/calendario')
def calendario():
    return render_template('calendario.html')

@app.route('/api/tareas', methods=['POST'])
def crear_tarea():
    data = request.get_json()
    print(f"Datos recibidos para crear_tarea: {data}")

    fecha = data.get('fecha')
    texto = data.get('texto')

    if not fecha or not texto:
        print("Error: Faltan datos (fecha o texto)")
        return jsonify({"error": "Faltan datos (fecha o texto)"}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        print(f"Error: Formato de fecha inválido para {fecha}. Se esperaba YYYY-MM-DD")
        return jsonify({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}), 400

    try:
        # Se añade la tarea con 'completada=False' por defecto gracias al modelo
        nueva_tarea = Tarea(fecha=fecha, texto=texto)
        db.session.add(nueva_tarea)
        db.session.commit()
        tarea_id = nueva_tarea.id
        print(f"Tarea '{texto}' guardada con ID: {tarea_id} para la fecha: {fecha}")
        # Asegúrate de devolver el estado 'completada' en la respuesta POST también
        return jsonify({"id": tarea_id, "fecha": fecha, "texto": texto, "completada": nueva_tarea.completada}), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error al insertar la tarea en la base de datos: {e}")
        return jsonify({"error": f"Error al guardar la tarea: {e}"}), 500

@app.route('/api/tareas/<fecha>', methods=['GET'])
def tareas_por_fecha(fecha):
    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}), 400

    # Cambiamos para obtener también el estado 'completada'
    tareas_db = Tarea.query.filter_by(fecha=fecha).all()
    tareas = [{"id": t.id, "texto": t.texto, "completada": t.completada} for t in tareas_db]
    return jsonify(tareas)

# ¡NUEVA RUTA API para marcar tareas como completadas/pendientes!
@app.route('/api/tareas/<int:tarea_id>/toggle_completada', methods=['PATCH'])
def toggle_completada(tarea_id):
    try:
        tarea = Tarea.query.get(tarea_id)
        if not tarea:
            return jsonify({"error": "Tarea no encontrada"}), 404

        tarea.completada = not tarea.completada # Invierte el estado actual
        db.session.commit()
        print(f"Tarea con ID {tarea_id} ahora completada: {tarea.completada}")
        return jsonify({"id": tarea.id, "completada": tarea.completada}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error al cambiar estado de la tarea: {e}")
        return jsonify({"error": f"Error al cambiar estado de la tarea: {e}"}), 500

@app.route('/api/tareas/<int:tarea_id>', methods=['DELETE'])
def borrar_tarea(tarea_id):
    try:
        tarea_a_borrar = Tarea.query.get(tarea_id)
        if tarea_a_borrar:
            db.session.delete(tarea_a_borrar)
            db.session.commit()
            print(f"Tarea con ID {tarea_id} eliminada.")
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": "Tarea no encontrada"}), 404
    except Exception as e:
        db.session.rollback()
        print(f"Error al borrar la tarea: {e}")
        return jsonify({"error": f"Error al borrar la tarea: {e}"}), 500

@app.route('/api/tareas-mes/<mes>', methods=['GET'])
def tareas_por_mes(mes):
    try:
        datetime.strptime(mes + '-01', '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Formato de mes inválido. Use YYYY-MM"}), 400

    fechas_distintas = db.session.query(Tarea.fecha).filter(Tarea.fecha.like(mes + '%')).distinct().all()
    fechas = [f[0] for f in fechas_distintas]
    return jsonify(fechas)

if __name__ == '__main__':
    init_db()
>>>>>>> 69ff5c517d33afb819bd9f2be1c4d971c5a2a6a8
    app.run(debug=True, host='0.0.0.0', port=5000)
