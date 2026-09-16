from django.core.validators import MinValueValidator
from django.db import models
from django.conf import settings


class Usuario(models.Model):
	cuenta = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="perfil_gimnasio",
	)
	nombre = models.CharField(max_length=120)
	email = models.EmailField(unique=True)
	fecha_registro = models.DateTimeField(auto_now_add=True)
	activo = models.BooleanField(default=True)

	class Meta:
		ordering = ["nombre"]
		indexes = [models.Index(fields=["nombre"]), models.Index(fields=["activo"])]

	def __str__(self):
		return self.nombre


class Entrenamiento(models.Model):
	nombre = models.CharField(max_length=120)
	descripcion = models.TextField(blank=True)
	notas = models.TextField(blank=True)
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
	usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="entrenamientos")
	entrenamiento = models.ForeignKey(
		Entrenamiento, on_delete=models.CASCADE, related_name="usuarios"
	)
	fecha_asignacion = models.DateTimeField(auto_now_add=True)

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
	notas = models.TextField(blank=True)

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
	notas = models.TextField(blank=True)

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
	notas = models.TextField(blank=True)

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
