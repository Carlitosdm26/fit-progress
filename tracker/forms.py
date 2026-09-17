import logging
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import Ejercicio, UsuarioEntrenamientoEjercicio

logger = logging.getLogger("tracker")


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
	username = forms.CharField(
		label="Email o usuario",
		widget=forms.TextInput(attrs={"autofocus": True}),
	)

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