import logging
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .models import (
	Ejercicio,
	Entrenamiento,
	EntrenamientoEjercicio,
	Serie,
	SesionEntrenamiento,
	UsuarioEntrenamiento,
	UsuarioEntrenamientoEjercicio,
)

logger = logging.getLogger("tracker")


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
	username = forms.CharField(
		label="Email o usuario",
		widget=forms.TextInput(attrs={"autofocus": True}),
	)

	def confirm_login_allowed(self, user):
		if not user.is_active:
			return
		super().confirm_login_allowed(user)

	def clean(self):
		username = (self.cleaned_data.get("username") or "").strip()
		password = self.cleaned_data.get("password")
		if username and password:
			user_model = get_user_model()
			user = None
			if "@" in username:
				user = user_model._default_manager.filter(email__iexact=username).first()
			else:
				user = user_model._default_manager.filter(username__iexact=username).first()
			if user is None:
				logger.warning(
					"Intento de login fallido: usuario inexistente. username=%s ip=%s",
					username,
					self.request.META.get("REMOTE_ADDR", "unknown"),
				)
				raise forms.ValidationError(
					_("Usuario o contraseña incorrectos."),
					code="invalid_login",
				)
			if not user.check_password(password):
				logger.warning(
					"Intento de login fallido: contraseña incorrecta. username=%s user_id=%s ip=%s",
					user.username,
					user.pk,
					self.request.META.get("REMOTE_ADDR", "unknown"),
				)
				raise forms.ValidationError(
					_("Usuario o contraseña incorrectos."),
					code="invalid_login",
				)
			self.user_cache = user
			self.confirm_login_allowed(user)
			return self.cleaned_data
		return super().clean()


class RegistroForm(UserCreationForm):
	email = forms.EmailField(label="Email", required=True)

	class Meta(UserCreationForm.Meta):
		model = get_user_model()
		fields = ("username", "email")
		labels = {
			"username": "Nombre de usuario",
			"email": "Email",
		}
		help_texts = {
			"username": "",
			"email": "",
		}
		error_messages = {
			"username": {"required": "Este campo es obligatorio."},
			"email": {"required": "Este campo es obligatorio."},
		}

	def clean_email(self):
		email = self.cleaned_data["email"].strip()
		if get_user_model().objects.filter(email__iexact=email).exists():
			raise forms.ValidationError("Ya existe una cuenta con ese email.")
		return email

	def clean_username(self):
		username = self.cleaned_data["username"].strip()
		if not username:
			raise forms.ValidationError("Este campo es obligatorio.")
		return username

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["password1"].label = "Contraseña"
		self.fields["password2"].label = "Confirmar contraseña"
		self.fields["password1"].help_text = ""
		self.fields["password2"].help_text = ""
		self.fields["password1"].error_messages["required"] = "Este campo es obligatorio."
		self.fields["password2"].error_messages["required"] = "Este campo es obligatorio."
		self.fields["password2"].error_messages["password_mismatch"] = "Las contraseñas no coinciden."


class AdminUsuarioCreationForm(UserCreationForm):
	email = forms.EmailField(label="Email")
	is_active = forms.BooleanField(label="Cuenta activa", initial=True, required=False)
	is_staff = forms.BooleanField(label="Acceso al panel", required=False)
	is_superuser = forms.BooleanField(label="Permisos totales", required=False)

	class Meta(UserCreationForm.Meta):
		model = get_user_model()
		fields = ("username", "email", "is_active", "is_staff", "is_superuser")
		labels = {
			"username": "Nombre de usuario",
			"email": "Email",
			"is_active": "Cuenta activa",
			"is_staff": "Acceso al panel",
			"is_superuser": "Permisos totales",
		}

	def __init__(self, *args, actor=None, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["password1"].label = "Contraseña"
		self.fields["password2"].label = "Repetir contraseña"
		if actor is not None and not actor.is_superuser:
			self.fields.pop("is_staff", None)
			self.fields.pop("is_superuser", None)

	def clean_email(self):
		email = self.cleaned_data["email"].strip()
		if get_user_model().objects.filter(email__iexact=email).exists():
			raise forms.ValidationError("Ya existe una cuenta con ese email.")
		return email

	def clean(self):
		cleaned_data = super().clean()
		if cleaned_data.get("is_superuser") and not cleaned_data.get("is_staff"):
			self.add_error("is_staff", "Un superusuario también necesita acceso al panel.")
		return cleaned_data


class AdminUsuarioUpdateForm(forms.ModelForm):
	password1 = forms.CharField(
		label="Nueva contraseña",
		required=False,
		widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
	)
	password2 = forms.CharField(
		label="Repetir contraseña",
		required=False,
		widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
	)
	class Meta:
		model = get_user_model()
		fields = ("username", "email", "is_active", "is_staff", "is_superuser")
		labels = {
			"username": "Nombre de usuario",
			"email": "Email",
			"is_active": "Cuenta activa",
			"is_staff": "Acceso al panel",
			"is_superuser": "Permisos totales",
		}

	def __init__(self, *args, actor=None, **kwargs):
		super().__init__(*args, **kwargs)
		if actor is not None and not actor.is_superuser:
			self.fields.pop("is_staff", None)
			self.fields.pop("is_superuser", None)

	def clean_email(self):
		email = self.cleaned_data["email"].strip()
		duplicates = get_user_model().objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
		if duplicates.exists():
			raise forms.ValidationError("Ya existe una cuenta con ese email.")
		return email

	def clean(self):
		cleaned_data = super().clean()
		password1 = cleaned_data.get("password1")
		password2 = cleaned_data.get("password2")
		if password1 or password2:
			if password1 != password2:
				self.add_error("password2", "Las contraseñas no coinciden.")
			elif password1:
				try:
					validate_password(password1, self.instance)
				except ValidationError as error:
					self.add_error("password1", error)
		if cleaned_data.get("is_superuser") and not cleaned_data.get("is_staff"):
			self.add_error("is_staff", "Un superusuario también necesita acceso al panel.")

		was_last_active_superuser = (
			self.instance.pk
			and self.instance.is_active
			and self.instance.is_staff
			and self.instance.is_superuser
			and not (
				cleaned_data.get("is_active")
				and cleaned_data.get("is_staff")
				and cleaned_data.get("is_superuser")
			)
			and not get_user_model().objects.filter(
				is_active=True, is_staff=True, is_superuser=True
			).exclude(pk=self.instance.pk).exists()
		)
		if was_last_active_superuser:
			self.add_error(None, "No se puede quitar el acceso al último superusuario activo.")
		return cleaned_data

	def save(self, commit=True):
		usuario = super().save(commit=False)
		if self.cleaned_data.get("password1"):
			usuario.set_password(self.cleaned_data["password1"])
		if commit:
			usuario.save()
			self.save_m2m()
		return usuario


class AdminEjercicioForm(forms.ModelForm):
	class Meta:
		model = Ejercicio
		fields = ("nombre", "grupo_muscular", "equipamiento", "descripcion", "activo")
		labels = {
			"nombre": "Nombre",
			"grupo_muscular": "Grupo muscular",
			"equipamiento": "Equipamiento",
			"descripcion": "Descripción",
			"activo": "Disponible para nuevas rutinas",
		}
		widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}

	def clean_nombre(self):
		nombre = self.cleaned_data["nombre"].strip()
		duplicates = Ejercicio.objects.filter(nombre__iexact=nombre).exclude(pk=self.instance.pk)
		if duplicates.exists():
			raise forms.ValidationError("Ya existe un ejercicio con ese nombre.")
		return nombre


class AdminEntrenamientoForm(forms.ModelForm):
	class Meta:
		model = Entrenamiento
		fields = ("nombre", "descripcion")
		labels = {"nombre": "Nombre de la rutina", "descripcion": "Descripción"}
		widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}


class AdminAsignacionForm(forms.ModelForm):
	class Meta:
		model = UsuarioEntrenamiento
		fields = ("usuario", "entrenamiento")
		labels = {"usuario": "Usuario", "entrenamiento": "Rutina"}

	def __init__(self, *args, entrenamiento=None, **kwargs):
		super().__init__(*args, **kwargs)
		if entrenamiento is not None:
			self.instance.entrenamiento = entrenamiento
			self.fields.pop("entrenamiento")
			self.fields["usuario"].queryset = self.fields["usuario"].queryset.filter(is_active=True)

	def clean(self):
		cleaned_data = super().clean()
		usuario = cleaned_data.get("usuario")
		entrenamiento = cleaned_data.get("entrenamiento") or self.instance.entrenamiento
		if usuario and entrenamiento and UsuarioEntrenamiento.objects.filter(
			usuario=usuario, entrenamiento=entrenamiento, activa=True
		).exclude(pk=self.instance.pk).exists():
			self.add_error("usuario", "Este usuario ya tiene asignada esta rutina.")
		return cleaned_data


class AdminEntrenamientoEjercicioForm(forms.ModelForm):
	class Meta:
		model = EntrenamientoEjercicio
		fields = ("ejercicio", "orden")
		labels = {"ejercicio": "Ejercicio", "orden": "Orden en la rutina"}

	def __init__(self, *args, entrenamiento, **kwargs):
		super().__init__(*args, **kwargs)
		self.entrenamiento = entrenamiento
		queryset = Ejercicio.objects.filter(activo=True)
		if self.instance.pk:
			queryset = Ejercicio.objects.filter(Q(activo=True) | Q(pk=self.instance.ejercicio_id))
		self.fields["ejercicio"].queryset = queryset.order_by("nombre")

	def clean(self):
		cleaned_data = super().clean()
		ejercicio = cleaned_data.get("ejercicio")
		orden = cleaned_data.get("orden")
		if ejercicio and EntrenamientoEjercicio.objects.filter(
			entrenamiento=self.entrenamiento, ejercicio=ejercicio
		).exclude(pk=self.instance.pk).exists():
			self.add_error("ejercicio", "Este ejercicio ya está en la rutina.")
		if orden and EntrenamientoEjercicio.objects.filter(
			entrenamiento=self.entrenamiento, orden=orden
		).exclude(pk=self.instance.pk).exists():
			self.add_error("orden", "Ese orden ya está ocupado en la rutina.")
		return cleaned_data


class AdminSesionForm(forms.ModelForm):
	class Meta:
		model = SesionEntrenamiento
		fields = ("usuario_entrenamiento", "fecha", "notas")
		labels = {
			"usuario_entrenamiento": "Usuario y rutina",
			"fecha": "Fecha y hora",
			"notas": "Notas",
		}
		widgets = {
			"fecha": forms.DateTimeInput(
				attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
			),
			"notas": forms.Textarea(attrs={"rows": 3}),
		}

	def __init__(self, *args, usuario=None, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["fecha"].input_formats = ["%Y-%m-%dT%H:%M"]
		if self.instance.pk:
			self.fields["usuario_entrenamiento"].disabled = True
			self.fields["usuario_entrenamiento"].help_text = "La cuenta y rutina de una sesión existente no se pueden cambiar."
		queryset = UsuarioEntrenamiento.objects.select_related("usuario", "entrenamiento")
		if usuario is not None:
			queryset = queryset.filter(usuario=usuario)
		self.fields["usuario_entrenamiento"].queryset = queryset.order_by(
			"usuario__username", "entrenamiento__nombre"
		)


class AdminSerieForm(forms.ModelForm):
	class Meta:
		model = Serie
		fields = ("usuario_entrenamiento_ejercicio", "numero_serie", "repeticiones", "peso")
		labels = {
			"usuario_entrenamiento_ejercicio": "Ejercicio de la rutina",
			"numero_serie": "Número de serie",
			"repeticiones": "Repeticiones",
			"peso": "Peso (kg)",
		}

	def __init__(self, *args, sesion, **kwargs):
		super().__init__(*args, **kwargs)
		self.sesion = sesion
		self.fields["usuario_entrenamiento_ejercicio"].queryset = (
			UsuarioEntrenamientoEjercicio.objects.filter(
				usuario_entrenamiento=sesion.usuario_entrenamiento
			).select_related("entrenamiento_ejercicio__ejercicio")
		)

	def clean(self):
		cleaned_data = super().clean()
		seleccion = cleaned_data.get("usuario_entrenamiento_ejercicio")
		numero = cleaned_data.get("numero_serie")
		if seleccion and numero and Serie.objects.filter(
			sesion_entrenamiento=self.sesion,
			usuario_entrenamiento_ejercicio=seleccion,
			numero_serie=numero,
		).exclude(pk=self.instance.pk).exists():
			self.add_error("numero_serie", "Ya existe ese número de serie para este ejercicio.")
		return cleaned_data


class EntrenamientoForm(forms.Form):
	nombre = forms.CharField(max_length=120, label="Nombre")
	descripcion = forms.CharField(
		label="Descripción", required=False, widget=forms.Textarea(attrs={"rows": 3})
	)
	ejercicios = forms.ModelMultipleChoiceField(
		label="Ejercicios",
		queryset=Ejercicio.objects.none(),
		required=True,
		widget=forms.CheckboxSelectMultiple,
		help_text="Selecciona al menos un ejercicio.",
	)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["ejercicios"].queryset = Ejercicio.objects.filter(activo=True)


class EjercicioForm(forms.ModelForm):
	class Meta:
		model = Ejercicio
		fields = ("nombre", "grupo_muscular", "equipamiento", "descripcion")
		labels = {
			"nombre": "Nombre del ejercicio",
			"grupo_muscular": "Grupo muscular",
			"equipamiento": "Material",
			"descripcion": "Indicaciones",
		}
		widgets = {
			"descripcion": forms.Textarea(attrs={"rows": 3}),
		}

	def clean_nombre(self):
		nombre = self.cleaned_data["nombre"].strip()
		if Ejercicio.objects.filter(nombre__iexact=nombre).exists():
			raise forms.ValidationError("Ya existe un ejercicio con ese nombre.")
		return nombre


class SesionForm(forms.Form):
	notas = forms.CharField(
		label="Notas de la sesión",
		required=False,
		widget=forms.Textarea(attrs={"rows": 3}),
	)

	def __init__(self, asignacion, sesion=None, editar_seleccion_id=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.exercise_rows = []
		existing_series = {}
		if sesion is not None:
			for serie in sesion.series.all():
				existing_series.setdefault(serie.usuario_entrenamiento_ejercicio_id, []).append(serie)
		selecciones = asignacion.ejercicios_elegidos.select_related(
			"entrenamiento_ejercicio__ejercicio"
		)
		for seleccion in selecciones:
			ejercicio = seleccion.entrenamiento_ejercicio.ejercicio
			series_existentes = existing_series.get(seleccion.pk, [])
			count_name = f"series_count_{seleccion.pk}"
			count_initial = len(series_existentes)
			self.fields[count_name] = forms.IntegerField(
				required=True,
				min_value=0,
				max_value=20,
				initial=count_initial,
				label="Número de series",
			)
			row = {
				"ejercicio": ejercicio,
				"seleccion": seleccion,
				"sets": [],
				"count_field": self[count_name],
				"count_name": count_name,
			}
			count_value = self.data.get(count_name) if self.is_bound else count_initial
			try:
				count_value = min(max(int(count_value or 0), 0), 20)
			except (TypeError, ValueError):
				count_value = 0
			for numero_serie in range(1, count_value + 1):
				reps_name = f"reps_{seleccion.pk}_{numero_serie}"
				peso_name = f"peso_{seleccion.pk}_{numero_serie}"
				serie_existente = next(
					(serie for serie in series_existentes if serie.numero_serie == numero_serie),
					None,
				)
				self.fields[reps_name] = forms.IntegerField(
					required=False,
					min_value=1,
					initial=serie_existente.repeticiones if serie_existente else None,
					label=f"Serie {numero_serie} - repeticiones",
				)
				self.fields[peso_name] = forms.DecimalField(
					required=False,
					min_value=Decimal("0"),
					max_digits=7,
					decimal_places=2,
					initial=serie_existente.peso if serie_existente else None,
					label=f"Serie {numero_serie} - peso (kg)",
				)
				row["sets"].append(
					{
						"number": numero_serie,
						"reps_field": self[reps_name],
						"peso_field": self[peso_name],
						"reps_name": reps_name,
						"peso_name": peso_name,
					}
				)
			self.exercise_rows.append(row)

	def clean(self):
		cleaned_data = super().clean()
		self.series_data = []
		for row in self.exercise_rows:
			for serie in row["sets"]:
				repeticiones = cleaned_data.get(serie["reps_name"])
				peso = cleaned_data.get(serie["peso_name"])
				if (repeticiones is None) != (peso is None):
					raise forms.ValidationError(
						f"Completa repeticiones y peso en la serie {serie['number']} de {row['ejercicio'].nombre}."
					)
				if repeticiones is not None and peso is not None:
					self.series_data.append(
						{
							"seleccion": row["seleccion"],
							"numero_serie": serie["number"],
							"repeticiones": repeticiones,
							"peso": peso,
						}
					)
		if not self.series_data:
			self.add_error(None, "Registra al menos una serie con repeticiones y peso.")
		return cleaned_data


class EjercicioSesionForm(forms.Form):
	ejercicio = forms.ModelChoiceField(
		queryset=UsuarioEntrenamientoEjercicio.objects.none(),
		label="Ejercicio",
		empty_label=None,
	)
	numero_series = forms.IntegerField(
		min_value=1, max_value=20, initial=0, label="Número de series"
	)
	notas = forms.CharField(
		label="Notas de la sesión",
		required=False,
		widget=forms.Textarea(attrs={"rows": 3}),
	)

	def __init__(self, asignacion, sesion=None, editar_seleccion_id=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.asignacion = asignacion
		self.sesion = sesion
		selecciones = asignacion.ejercicios_elegidos.select_related(
			"entrenamiento_ejercicio__ejercicio"
		)
		selected_id = str(editar_seleccion_id) if editar_seleccion_id else None
		self.fields["ejercicio"].queryset = selecciones.exclude(
			pk__in=sesion.series.values_list("usuario_entrenamiento_ejercicio_id", flat=True)
		) if sesion is not None else selecciones
		if selected_id:
			self.fields["ejercicio"].queryset = selecciones.filter(pk=selected_id)
			self.fields["ejercicio"].initial = selected_id
		existing_series = []
		if sesion is not None and selected_id:
			existing_series = list(
				sesion.series.filter(usuario_entrenamiento_ejercicio_id=selected_id).order_by("numero_serie")
			)
		count_value = self.data.get("numero_series") if self.is_bound else len(existing_series)
		try:
			count_value = min(max(int(count_value or 0), 0), 20)
		except (TypeError, ValueError):
			count_value = 0
		self.series_fields = []
		for numero_serie in range(1, count_value + 1):
			reps_name = f"reps_{numero_serie}"
			peso_name = f"peso_{numero_serie}"
			serie_existente = next(
				(serie for serie in existing_series if serie.numero_serie == numero_serie), None
			)
			self.fields[reps_name] = forms.IntegerField(
				required=False,
				min_value=1,
				initial=serie_existente.repeticiones if serie_existente else None,
				label=f"Serie {numero_serie} - repeticiones",
			)
			self.fields[peso_name] = forms.DecimalField(
				required=False,
				min_value=Decimal("0"),
				max_digits=7,
				decimal_places=2,
				initial=serie_existente.peso if serie_existente else None,
				label=f"Serie {numero_serie} - peso (kg)",
			)
			self.series_fields.append(
				{
					"number": numero_serie,
					"reps_field": self[reps_name],
					"peso_field": self[peso_name],
				}
			)

	def clean(self):
		cleaned_data = super().clean()
		self.series_data = []
		for serie in self.series_fields:
			repeticiones = cleaned_data.get(f"reps_{serie['number']}")
			peso = cleaned_data.get(f"peso_{serie['number']}")
			if (repeticiones is None) != (peso is None):
				raise forms.ValidationError(
					f"Completa repeticiones y peso en la serie {serie['number']}."
				)
			if repeticiones is not None and peso is not None:
				self.series_data.append(
					{
						"numero_serie": serie["number"],
						"repeticiones": repeticiones,
						"peso": peso,
					}
				)
		if not self.series_data:
			self.add_error(None, "Registra al menos una serie con repeticiones y peso.")
		return cleaned_data