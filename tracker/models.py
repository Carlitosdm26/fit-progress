from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import Group, Permission, PermissionsMixin
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class UsuarioManager(BaseUserManager):
	use_in_migrations = True

	def create_user(self, username, email="", password=None, **extra_fields):
		if not username:
			raise ValueError("El nombre de usuario es obligatorio.")
		user = self.model(
			username=username,
			email=self.normalize_email(email),
			**extra_fields,
		)
		user.set_password(password)
		user.save(using=self._db)
		return user

	def create_superuser(self, username, email="", password=None, **extra_fields):
		extra_fields.setdefault("is_staff", True)
		extra_fields.setdefault("is_superuser", True)
		extra_fields.setdefault("is_active", True)
		if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
			raise ValueError("El superusuario debe tener permisos de administraci??n.")
		return self.create_user(username, email, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
	id = models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")
	username = models.CharField(max_length=150, unique=True)
	email = models.EmailField(blank=True)
	is_staff = models.BooleanField(default=False)
	is_active = models.BooleanField(default=True)
	date_joined = models.DateTimeField(default=timezone.now)
	groups = models.ManyToManyField(
		Group,
		blank=True,
		db_table="auth_user_groups",
		related_name="user_set",
		related_query_name="user",
	)
	user_permissions = models.ManyToManyField(
		Permission,
		blank=True,
		db_table="auth_user_user_permissions",
		related_name="user_set",
		related_query_name="user",
	)
	objects = UsuarioManager()

	USERNAME_FIELD = "username"
	REQUIRED_FIELDS = ["email"]

	def __str__(self):
		return self.username

	class Meta:
		db_table = "auth_user"


class DatoArchivado(models.Model):
	modelo = models.CharField(max_length=100)
	registro_id = models.PositiveBigIntegerField()
	campo = models.CharField(max_length=100)
	valor = models.TextField()

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["modelo", "registro_id", "campo"],
				name="unique_dato_archivado",
			)
		]
		ordering = ["modelo", "registro_id", "campo"]


class PerfilUsuario(models.Model):
	usuario = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="perfil_admin",
	)
	descripcion = models.TextField("Descripci??n", blank=True)

	def __str__(self):
		return f"Perfil de {self.usuario.username}"


class Entrenamiento(models.Model):
	nombre = models.CharField(max_length=120)
	descripcion = models.TextField(blank=True)
	fecha_creacion = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["nombre"]
		indexes = [models.Index(fields=["nombre"])]

	def __str__(self):
		return self.nombre


class Ejercicio(models.Model):
	nombre = models.CharField(max_length=120)
	descripcion = models.TextField(blank=True)
	equipamiento = models.CharField(max_length=120, blank=True)
	grupo_muscular = models.CharField(max_length=80)
	activo = models.BooleanField(default=True)

	class Meta:
		ordering = ["nombre"]
		indexes = [
			models.Index(fields=["nombre"]),
			models.Index(fields=["grupo_muscular"]),
			models.Index(fields=["activo"]),
		]

	def __str__(self):
		return self.nombre


class UsuarioEntrenamiento(models.Model):
	usuario = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="entrenamientos"
	)
	entrenamiento = models.ForeignKey(
		Entrenamiento, on_delete=models.CASCADE, related_name="usuarios"
	)
	fecha_asignacion = models.DateTimeField(auto_now_add=True)
	activa = models.BooleanField(default=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["usuario", "entrenamiento"], name="unique_usuario_entrenamiento"
			)
		]
		indexes = [models.Index(fields=["usuario"]), models.Index(fields=["entrenamiento"])]

	def __str__(self):
		return f"{self.usuario} - {self.entrenamiento}"


class EntrenamientoEjercicio(models.Model):
	entrenamiento = models.ForeignKey(
		Entrenamiento, on_delete=models.CASCADE, related_name="ejercicios"
	)
	ejercicio = models.ForeignKey(
		Ejercicio, on_delete=models.PROTECT, related_name="entrenamientos"
	)
	orden = models.PositiveIntegerField(validators=[MinValueValidator(1)])

	class Meta:
		ordering = ["orden"]
		constraints = [
			models.UniqueConstraint(
				fields=["entrenamiento", "ejercicio"], name="unique_entrenamiento_ejercicio"
			),
			models.UniqueConstraint(
				fields=["entrenamiento", "orden"], name="unique_entrenamiento_orden"
			),
		]
		indexes = [models.Index(fields=["entrenamiento"]), models.Index(fields=["ejercicio"])]

	def __str__(self):
		return f"{self.entrenamiento}: {self.ejercicio}"


class UsuarioEntrenamientoEjercicio(models.Model):
	usuario_entrenamiento = models.ForeignKey(
		UsuarioEntrenamiento, on_delete=models.CASCADE, related_name="ejercicios_elegidos"
	)
	entrenamiento_ejercicio = models.ForeignKey(
		EntrenamientoEjercicio, on_delete=models.PROTECT, related_name="elecciones"
	)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["usuario_entrenamiento", "entrenamiento_ejercicio"],
				name="unique_usuario_entrenamiento_ejercicio",
			)
		]
		indexes = [
			models.Index(fields=["usuario_entrenamiento"]),
			models.Index(fields=["entrenamiento_ejercicio"]),
		]

	def __str__(self):
		return f"{self.usuario_entrenamiento}: {self.entrenamiento_ejercicio.ejercicio}"


class SesionEntrenamiento(models.Model):
	usuario_entrenamiento = models.ForeignKey(
		UsuarioEntrenamiento, on_delete=models.CASCADE, related_name="sesiones"
	)
	fecha = models.DateTimeField()
	notas = models.TextField(blank=True)

	class Meta:
		ordering = ["-fecha"]
		indexes = [models.Index(fields=["usuario_entrenamiento", "-fecha"])]

	def __str__(self):
		return f"{self.usuario_entrenamiento} - {self.fecha:%Y-%m-%d}"


class Serie(models.Model):
	sesion_entrenamiento = models.ForeignKey(
		SesionEntrenamiento, on_delete=models.CASCADE, related_name="series"
	)
	usuario_entrenamiento_ejercicio = models.ForeignKey(
		UsuarioEntrenamientoEjercicio, on_delete=models.PROTECT, related_name="series"
	)
	numero_serie = models.PositiveIntegerField(validators=[MinValueValidator(1)])
	repeticiones = models.PositiveIntegerField(validators=[MinValueValidator(1)])
	peso = models.DecimalField(
		max_digits=7, decimal_places=2, validators=[MinValueValidator(0)]
	)

	class Meta:
		ordering = ["numero_serie"]
		constraints = [
			models.UniqueConstraint(
				fields=[
					"sesion_entrenamiento",
					"usuario_entrenamiento_ejercicio",
					"numero_serie",
				],
				name="unique_serie_en_sesion",
			)
		]
		indexes = [
			models.Index(fields=["sesion_entrenamiento"]),
			models.Index(fields=["usuario_entrenamiento_ejercicio"]),
		]

	def __str__(self):
		return f"Serie {self.numero_serie}: {self.peso} kg x {self.repeticiones}"
