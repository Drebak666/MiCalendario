import tkinter as tk
from tkinter import messagebox
from tkcalendar import Calendar
from datetime import datetime

# Diccionarios para nombres de días y meses
dias_semana = {
    0: "Lun", 1: "Mar", 2: "Mié", 3: "Jue", 4: "Vie", 5: "Sáb", 6: "Dom"
}
meses = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}

# Fecha actual
hoy = datetime.now()
dia_semana = dias_semana[hoy.weekday()]
dia = hoy.day
mes = meses[hoy.month]
año = hoy.year
fecha_formateada = f"{dia_semana} {dia} de {mes} de {año}"

# Crear ventana
ventana = tk.Tk()
ventana.title("Agenda Personal")
ventana.geometry("400x350")
ventana.configure(bg="white")

# --- Pantalla Inicial ---
frame_inicial = tk.Frame(ventana, bg="white")
frame_inicial.pack(fill="both", expand=True)

etiqueta_fecha = tk.Label(frame_inicial, text=fecha_formateada, font=("Helvetica", 16, "bold"), bg="white")
etiqueta_fecha.pack(pady=10)

def mostrar_calendario():
    frame_inicial.pack_forget()
    frame_calendario.pack(fill="both", expand=True)

btn_calendario = tk.Button(
    frame_inicial,
    text="Calendario",
    bg="#4a90e2",
    fg="white",
    font=("Helvetica", 14, "bold"),
    relief="raised",
    borderwidth=4,
    activebackground="#357ABD",
    activeforeground="white",
    command=mostrar_calendario
)
btn_calendario.pack(pady=10)

def on_enter(e):
    btn_calendario['bg'] = '#357ABD'

def on_leave(e):
    btn_calendario['bg'] = '#4a90e2'

btn_calendario.bind("<Enter>", on_enter)
btn_calendario.bind("<Leave>", on_leave)

# --- Pantalla Calendario ---
frame_calendario = tk.Frame(ventana, bg="white")

def volver_inicio():
    frame_calendario.pack_forget()
    frame_inicial.pack(fill="both", expand=True)

# Botón volver arriba a la derecha
btn_volver = tk.Button(
    frame_calendario,
    text="Volver",
    command=volver_inicio,
    bg="#4a90e2",
    fg="white",
    font=("Helvetica", 10, "bold"),
    relief="raised",
    borderwidth=3,
    activebackground="#357ABD",
    activeforeground="white"
)
btn_volver.pack(anchor="ne", padx=10, pady=10)

# Calendario con día actual resaltado
cal = Calendar(
    frame_calendario,
    selectmode='none',
    year=año,
    month=hoy.month,
    day=hoy.day,
    background='white',
    disabledbackground='white',
    bordercolor='gray',
    headersbackground='#4a90e2',
    normalbackground='white',
    normalforeground='black',
    weekendbackground='white',
    weekendforeground='black',
    selectbackground='#4a90e2',
    selectforeground='white'
)
cal.pack(padx=20, pady=10, fill="both", expand=True)

ventana.mainloop()
