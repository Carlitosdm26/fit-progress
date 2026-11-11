# Fit Progress

Aplicación web Django para gestionar rutinas de gimnasio y registrar el progreso de cada usuario.

## Funcionalidades

- Login individual para cada usuario.
- Registro público con cuentas inactivas hasta que un administrador las active.
- Catálogo compartido de ejercicios, filtrable por grupo muscular y ampliable por cualquier usuario con una cuenta activa.
- Creación y edición de rutinas personales; Administración puede asignarlas mediante copias independientes.
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

El script verifica Python y `.env`, crea `.venv` si falta, instala dependencias, comprueba Django, aplica migraciones y arranca el servidor local en `0.0.0.0:8000`. En un despliegue nuevo, `migrate` crea las tablas de la aplicación dentro de la base configurada. La base MySQL indicada por `DB_NAME` debe existir previamente y el usuario configurado necesita permisos para crear y modificar tablas.

Pulsa `Ctrl+C` para detener el servidor limpiamente.

Direcciones locales:

- Aplicación: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Login: [http://127.0.0.1:8000/login/](http://127.0.0.1:8000/login/)
- Administración: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

## Gestión de cuentas

El registro público crea cuentas inactivas. Los usuarios pueden iniciar sesión, pero solo verán un aviso hasta que un administrador active sus cuentas desde `/admin/`.

Los administradores también pueden crear cuentas directamente desde `Auth > Users` y decidir si deben estar activas.

Si todavía no existe un superusuario:

```bash
.venv/bin/python manage.py createsuperuser
```

Después, crea el usuario en `Auth > Users` desde `/admin/`, indicando su nombre y email. La cuenta de Django guarda tanto los datos de acceso como el perfil deportivo; no hace falta asignar un grupo ni crear o vincular un registro separado en `Tracker > Usuarios`.

Las cuentas inactivas pueden iniciar sesión, pero solo verán un aviso para contactar con un administrador; no podrán acceder a las páginas de la aplicación hasta que se active su cuenta.

Antes de desplegar la migración que unifica las tablas, haz una copia de seguridad de la base de datos. Los perfiles sin cuenta vinculada se convierten en cuentas con contraseña no utilizable; el superusuario deberá establecerles una contraseña desde el panel de administración.

## Administración de rutinas y actividad

En `/admin/`, el panel de operaciones permite buscar usuarios, editar el catálogo de ejercicios, las rutinas y las sesiones. La acción `Ver` abre la ficha de solo lectura de cada usuario, con sus rutinas y sus diez sesiones más recientes; la edición de cuenta queda como acción aparte. Desde una rutina se ven los usuarios asignados y se pueden abrir sus sesiones. El listado de sesiones se puede filtrar por usuario y por rutina para localizar cualquier registro. En móvil, el menú se abre con el botón de tres líneas y la barra superior incluye un acceso de vuelta a la aplicación.

Un superusuario puede eliminar una cuenta escribiendo su nombre para confirmar; esto elimina también sus rutinas, sesiones y series. No se permite eliminar la propia cuenta desde la que se administra. En el detalle de una sesión se puede eliminar la sesión completa y sus series, sin borrar la rutina. Si la rutina ya estaba marcada como eliminada y se borra su última sesión, también se limpia definitivamente al quedarse sin historial. En el catálogo se pueden eliminar ejercicios que no estén asignados a ninguna rutina y no tengan historial protegido; si un ejercicio está en rutinas, el panel muestra cuáles son y si conservan series, para saber si puede retirarse o debe mantenerse por el historial.

Desde Administración se puede asignar una rutina a un usuario creando una copia independiente, con nombre y fecha de creación propios. El propietario se registra en `UsuarioEntrenamiento`; la copia no conserva una referencia a la rutina de origen. Desasignar una rutina personal la oculta de la cuenta, pero conserva sus sesiones e historial. En una sesión se pueden corregir la fecha y las notas, y añadir o editar series. Los ejercicios del catálogo se pueden pausar sin borrar el historial asociado.

## Flujo de usuario

1. El usuario inicia sesión en `/login/`.
2. En el dashboard pulsa `Crear entrenamiento`.
3. Escribe el nombre y, si quieres, selecciona ejercicios. También puedes dejar la rutina vacía y completarla desde `Ejercicios`.
4. En `Mis rutinas` pulsa `Registrar sesión`.
5. Selecciona un ejercicio, indica el número de series y completa las repeticiones y el peso.
6. Guarda el ejercicio y vuelve a la misma sesión para añadir el siguiente.
7. Para corregir un ejercicio ya guardado, pulsa `Editar ejercicio`.
8. Para modificar una rutina o una sesión, entra en su pantalla de edición.

Desde `Ejercicios`, cualquier usuario con sesión iniciada y cuenta activa puede añadir ejercicios al catálogo compartido. Al desplegar un ejercicio, puede añadirlo a cualquiera de sus rutinas activas donde todavía no esté; el cambio solo afecta a esa rutina personal. También puede añadir o quitar ejercicios desde la edición de su rutina. Si quita un ejercicio que ya tiene series registradas, deja de estar disponible para futuras sesiones, pero el historial anterior permanece visible. Los nombres duplicados no se aceptan.

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
- `Entrenamiento`: definición de una rutina.
- `Ejercicio`: catálogo de ejercicios.
- `UsuarioEntrenamiento`: asignación de una rutina a un usuario.
- `EntrenamientoEjercicio`: ejercicios incluidos en una rutina y su orden.
- `UsuarioEntrenamientoEjercicio`: ejercicio elegido por el usuario para esa rutina.
- `SesionEntrenamiento`: una realización concreta de una rutina.
- `Serie`: repeticiones, peso y número de serie realizados.

`UsuarioEntrenamiento` relaciona cada rutina con su propietario. Al asignarla a otra persona se crea un nuevo `Entrenamiento` y se copian sus ejercicios; la copia es independiente y no guarda una clave foránea a la rutina anterior.

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