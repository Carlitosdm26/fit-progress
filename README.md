# Fit Progress

Aplicación web Django para gestionar rutinas de gimnasio y registrar el progreso de cada usuario.

## Funcionalidades

- Login individual para cada usuario.
- Cuentas creadas únicamente por un superusuario desde el panel de administración.
- Catálogo de ejercicios activos, filtrable por grupo muscular.
- Creación y edición de rutinas.
- Registro progresivo de una sesión: se guarda un ejercicio cada vez.
- Número variable de series por ejercicio, con repeticiones y peso decimal en kilogramos.
- Edición de ejercicios ya registrados dentro de una sesión.
- Eliminación controlada de rutinas, sesiones o ejercicios de una sesión.
- Cada usuario solo puede consultar y modificar sus propios datos.

## Requisitos

- Python 3.10 o superior.
- MySQL accesible desde la máquina local.
- Credenciales de la base de datos en `.env`.

## Configuración

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Copia `.env.example` como `.env` y completa la configuración:

```env
DJANGO_SECRET_KEY=una-clave-secreta
DB_ENGINE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=usuario_mysql
DB_PASSWORD=contraseña_mysql
DB_NAME=fit_progress
```

No subas `.env` al repositorio. Contiene credenciales y está excluido mediante `.gitignore`.

## Arranque

### En contenedor

El contenedor escucha en el puerto 80 y Docker lo publica en el puerto 80 del servidor:

```bash
docker compose up --build -d
```

La aplicación estará disponible en [http://localhost/](http://localhost/).

### En local

La forma recomendada de arrancar la aplicación es:

```bash
./run.sh
```

El script verifica Python y `.env`, crea `.venv` si falta, instala dependencias, comprueba Django, aplica migraciones y arranca el servidor local en `0.0.0.0:8000`.

Pulsa `Ctrl+C` para detener el servidor limpiamente.

Direcciones locales:

- Aplicación: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Login: [http://127.0.0.1:8000/login/](http://127.0.0.1:8000/login/)
- Administración: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

## Gestión de cuentas

El registro público está desactivado. Solo el superusuario puede crear cuentas.

Si todavía no existe un superusuario:

```bash
.venv/bin/python manage.py createsuperuser
```

Después, crea el usuario en `Auth > Users` desde `/admin/`, indicando su nombre y email. En la sección de permisos, asígnale el grupo `Usuarios de gimnasio` para habilitar el acceso a la aplicación. La cuenta de Django guarda tanto los datos de acceso como el perfil; ya no hay que crear ni vincular un registro separado en `Tracker > Usuarios`.

Antes de desplegar la migración que unifica las tablas, haz una copia de seguridad de la base de datos. Los perfiles sin cuenta vinculada se convierten en cuentas con contraseña no utilizable; el superusuario deberá establecerles una contraseña desde el panel de administración.

## Flujo de usuario

1. El usuario inicia sesión en `/login/`.
2. En el dashboard pulsa `Crear entrenamiento`.
3. Escribe el nombre y selecciona los ejercicios. El desplegable permite filtrar por grupo muscular.
4. En `Mis rutinas` pulsa `Registrar sesión`.
5. Selecciona un ejercicio, indica el número de series y completa las repeticiones y el peso.
6. Guarda el ejercicio y vuelve a la misma sesión para añadir el siguiente.
7. Para corregir un ejercicio ya guardado, pulsa `Editar ejercicio`.
8. Para modificar una rutina o una sesión, entra en su pantalla de edición.

Ejemplo:

```text
Press banca
	Serie 1: 10 repeticiones, 60 kg
	Serie 2: 8 repeticiones, 65 kg

Press inclinado
	Serie 1: 12 repeticiones, 20 kg
```

## Eliminación de datos

Los botones de eliminar no aparecen en el dashboard principal. Están disponibles dentro de las pantallas de edición y solicitan confirmación.

- `Editar rutina`: elimina la rutina y sus sesiones si pertenecen al usuario.
- `Editar sesión`: elimina la sesión completa.
- Ejercicio guardado dentro de una sesión: elimina sus series de esa sesión.

Las acciones de borrado se realizan mediante `POST` y requieren autenticación. Los ejercicios del catálogo se protegen mediante baja lógica con `activo` para conservar el historial.

## Modelo principal

- `User` de Django: datos de acceso y perfil deportivo en una sola cuenta.
- `Entrenamiento`: rutina reutilizable.
- `Ejercicio`: catálogo de ejercicios.
- `UsuarioEntrenamiento`: asignación de una rutina a un usuario.
- `EntrenamientoEjercicio`: ejercicios incluidos en una rutina y su orden.
- `UsuarioEntrenamientoEjercicio`: ejercicio elegido por el usuario para esa rutina.
- `SesionEntrenamiento`: una realización concreta de una rutina.
- `Serie`: repeticiones, peso y número de serie realizados.

El peso se almacena como decimal y la unidad inicial es el kilogramo. Las restricciones de base de datos evitan relaciones y series duplicadas.

## Comprobaciones

Comprobar la configuración:

```bash
.venv/bin/python manage.py check
```

Ejecutar las pruebas usando una base temporal SQLite, sin tocar los datos reales de MySQL:

```bash
DB_ENGINE=sqlite .venv/bin/python manage.py test
```

El usuario de Clever Cloud puede no tener permisos para crear bases de datos `test_*`; por eso las pruebas se fuerzan a SQLite. La aplicación normal sigue usando MySQL porque `.env` mantiene `DB_ENGINE=mysql`.