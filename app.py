from flask import Flask, render_template
import datetime
import locale

app = Flask(__name__)

# Poner la localización en español (si da error, comenta esta línea)
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    pass  # En Windows a veces no funciona

@app.route('/')
def inicio():
    hoy = datetime.datetime.now()
    fecha_actual = hoy.strftime('%A %d de %B de %Y').capitalize()
    return render_template('index.html', fecha_actual=fecha_actual)

@app.route('/calendario')
def calendario():
    return render_template('calendario.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
