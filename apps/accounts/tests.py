import shutil
import tempfile
from io import BytesIO

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.catalog.models import Area, Sucursal
from .models import FotoPerfil, Usuario

PASSWORD = "pw-segura-123"


class LoginTests(TestCase):
    def setUp(self):
        self.area = Area.objects.create(nombre="Ventas")
        self.sucursal = Sucursal.objects.create(nombre="Central")
        self.user = Usuario.objects.create_user(
            "Ana@Empresa.com", "Ana", PASSWORD, area=self.area, sucursal=self.sucursal
        )

    def test_login_correcto_no_distingue_mayusculas(self):
        r = self.client.post(reverse("login"), {"correo": "ana@empresa.com", "password": PASSWORD})
        self.assertRedirects(r, reverse("panel_inicio"), fetch_redirect_response=False)

    def test_password_incorrecta(self):
        r = self.client.post(reverse("login"), {"correo": "ana@empresa.com", "password": "mal"})
        self.assertContains(r, "incorrectos")

    def test_usuario_inactivo_no_entra(self):
        Usuario.objects.filter(pk=self.user.pk).update(activo=False)
        r = self.client.post(reverse("login"), {"correo": "ana@empresa.com", "password": PASSWORD})
        self.assertContains(r, "incorrectos")

    def test_respeta_next_seguro_y_bloquea_externo(self):
        r = self.client.post(reverse("login"), {"correo": "ana@empresa.com", "password": PASSWORD, "next": "/tickets/nuevo/"})
        self.assertRedirects(r, "/tickets/nuevo/", fetch_redirect_response=False)
        self.client.logout()
        r = self.client.post(reverse("login"), {"correo": "ana@empresa.com", "password": PASSWORD, "next": "https://malo.com/"})
        self.assertRedirects(r, reverse("panel_inicio"), fetch_redirect_response=False)

    def test_logout_solo_por_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        r = self.client.post(reverse("logout"))
        self.assertRedirects(r, reverse("login"))


class GestionUsuariosTests(TestCase):
    def setUp(self):
        self.area = Area.objects.create(nombre="Ventas")
        self.sucursal = Sucursal.objects.create(nombre="Central")
        self.admin = Usuario.objects.create_user("admin@t.com", "Admin", PASSWORD, rol="SUPERADMIN", area=self.area)
        self.user = Usuario.objects.create_user(
            "u@t.com", "User", PASSWORD, area=self.area, sucursal=self.sucursal
        )

    def test_usuario_normal_no_accede_a_gestion(self):
        self.client.force_login(self.user)
        for nombre in ("lista_usuarios", "nuevo_usuario"):
            self.assertRedirects(self.client.get(reverse(nombre)), reverse("lista_tickets"))
        r = self.client.post(reverse("cambiar_estado_usuario", args=[self.admin.pk]))
        self.assertRedirects(r, reverse("lista_tickets"))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.activo)

    def test_crear_usuario_guarda_password_con_hash(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("nuevo_usuario"), {
            "nombre": "Nuevo", "correo": "nuevo@t.com", "rol": "USUARIO", "area": self.area.pk,
            "sucursal": self.sucursal.pk,
            "password1": "Clave-Larga-987", "password2": "Clave-Larga-987"})
        self.assertRedirects(r, reverse("lista_usuarios"))
        nuevo = Usuario.objects.get(correo="nuevo@t.com")
        self.assertNotEqual(nuevo.password, "Clave-Larga-987")
        self.assertTrue(nuevo.check_password("Clave-Larga-987"))

    def test_correo_duplicado_sin_importar_mayusculas(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("nuevo_usuario"), {
            "nombre": "X", "correo": "U@T.COM", "rol": "USUARIO", "area": self.area.pk,
            "password1": "Clave-Larga-987", "password2": "Clave-Larga-987"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("correo", r.context["form"].errors)

    def test_area_es_obligatoria(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("nuevo_usuario"), {
            "nombre": "X", "correo": "x@t.com", "rol": "USUARIO",
            "password1": "Clave-Larga-987", "password2": "Clave-Larga-987"})
        self.assertIn("area", r.context["form"].errors)

    def test_desactivar_y_reactivar_otro_usuario(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("cambiar_estado_usuario", args=[self.user.pk]))
        self.user.refresh_from_db()
        self.assertFalse(self.user.activo)
        self.client.post(reverse("cambiar_estado_usuario", args=[self.user.pk]))
        self.user.refresh_from_db()
        self.assertTrue(self.user.activo)

    def test_admin_no_puede_desactivarse_ni_quitarse_el_rol(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("cambiar_estado_usuario", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.activo)
        self.client.post(reverse("editar_usuario", args=[self.admin.pk]), {
            "nombre": "Admin", "correo": "admin@t.com", "rol": "USUARIO", "area": self.area.pk,
            "sucursal": self.sucursal.pk})
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, "SUPERADMIN")
        self.assertTrue(self.admin.activo)

    def test_editar_cambia_password_solo_si_se_escribe(self):
        self.client.force_login(self.admin)
        base = {
            "nombre": "User 2", "correo": "u@t.com", "rol": "USUARIO", "area": self.area.pk,
            "sucursal": self.sucursal.pk, "activo": "on",
        }
        self.client.post(reverse("editar_usuario", args=[self.user.pk]), base)
        self.user.refresh_from_db()
        self.assertEqual(self.user.nombre, "User 2")
        self.assertTrue(self.user.check_password(PASSWORD))
        self.client.post(reverse("editar_usuario", args=[self.user.pk]),
                         {**base, "password1": "Otra-Clave-555", "password2": "Otra-Clave-555"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Otra-Clave-555"))

    def test_tecnico_migrado_ya_no_existe_como_opcion(self):
        self.assertEqual(
            {v for v, _ in Usuario.Rol.choices},
            {"SUPERADMIN", "ENCARGADO", "BECARIO", "USUARIO"},
        )


class CorreoObligatorioTests(TestCase):
    def setUp(self):
        self.area = Area.objects.create(nombre="Ventas")
        self.sucursal = Sucursal.objects.create(nombre="Central")
        self.admin = Usuario.objects.create_user("admin@t.com", "Admin", PASSWORD, rol="SUPERADMIN", area=self.area)
        self.client.force_login(self.admin)

    def datos(self, **extra):
        datos = {
            "nombre": "Nuevo", "correo": "nuevo@t.com", "rol": "USUARIO", "area": self.area.pk,
            "sucursal": self.sucursal.pk,
            "password1": "Clave-Larga-987", "password2": "Clave-Larga-987",
        }
        datos.update(extra)
        return datos

    def test_no_se_puede_crear_usuario_ni_admin_sin_correo(self):
        for rol in ("USUARIO", "SUPERADMIN"):
            r = self.client.post(reverse("nuevo_usuario"), self.datos(correo="", rol=rol))
            self.assertEqual(r.status_code, 200)
            self.assertIn("correo", r.context["form"].errors)
        self.assertEqual(Usuario.objects.count(), 1)

    def test_correo_solo_con_espacios_no_vale(self):
        r = self.client.post(reverse("nuevo_usuario"), self.datos(correo="   "))
        self.assertIn("correo", r.context["form"].errors)

    def test_correo_con_formato_invalido_no_vale(self):
        r = self.client.post(reverse("nuevo_usuario"), self.datos(correo="no-es-un-correo"))
        self.assertIn("correo", r.context["form"].errors)

    def test_no_se_puede_quitar_el_correo_al_editar(self):
        otro = Usuario.objects.create_user(
            "otro@t.com", "Otro", PASSWORD, area=self.area, sucursal=self.sucursal
        )
        r = self.client.post(reverse("editar_usuario", args=[otro.pk]), {
            "nombre": "Otro", "correo": "", "rol": "USUARIO", "area": self.area.pk,
            "sucursal": self.sucursal.pk, "activo": "on",
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn("correo", r.context["form"].errors)
        otro.refresh_from_db()
        self.assertEqual(otro.correo, "otro@t.com")

    def test_create_user_sin_correo_falla(self):
        for vacio in ("", "   ", None):
            with self.assertRaises(ValueError):
                Usuario.objects.create_user(vacio, "X", PASSWORD, area=self.area)

    def test_la_base_rechaza_correo_vacio(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Usuario.objects.create(correo="", nombre="X", area=self.area)

    def test_la_base_rechaza_correos_que_solo_cambian_en_mayusculas(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Usuario.objects.create(correo="ADMIN@T.COM", nombre="X", area=self.area)


def imagen_prueba(nombre="foto.png", tamano=(400, 300), formato="PNG", color="blue"):
    buffer = BytesIO()
    Image.new("RGB", tamano, color).save(buffer, format=formato)
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type=f"image/{formato.lower()}")


class FotoPerfilTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._carpeta_media = tempfile.mkdtemp()
        cls._cambio_media = override_settings(MEDIA_ROOT=cls._carpeta_media)
        cls._cambio_media.enable()

    @classmethod
    def tearDownClass(cls):
        cls._cambio_media.disable()
        shutil.rmtree(cls._carpeta_media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.area = Area.objects.create(nombre="Ventas")
        self.sucursal = Sucursal.objects.create(nombre="Central")
        self.user = Usuario.objects.create_user(
            "ana@t.com", "Ana", PASSWORD, area=self.area, sucursal=self.sucursal
        )
        self.client.force_login(self.user)

    def subir(self, archivo):
        return self.client.post(reverse("mi_perfil"), {"foto": archivo})

    def test_subir_foto_la_guarda_cuadrada_en_disco(self):
        r = self.subir(imagen_prueba())
        self.assertRedirects(r, reverse("mi_perfil"))
        foto = FotoPerfil.objects.get(usuario=self.user)
        self.assertTrue(foto.archivo.name.startswith(f"fotos/{self.user.pk}/"))
        with default_storage.open(foto.archivo.name) as f:
            self.assertEqual(Image.open(f).size, (256, 256))

    def test_un_archivo_que_no_es_imagen_se_rechaza(self):
        falso = SimpleUploadedFile("foto.jpg", b"esto no es una imagen", content_type="image/jpeg")
        r = self.subir(falso)
        self.assertEqual(r.status_code, 200)
        self.assertIn("foto", r.context["form"].errors)
        self.assertFalse(FotoPerfil.objects.exists())

    def test_una_imagen_de_mas_de_5_mb_se_rechaza(self):
        r = self.subir(imagen_prueba("grande.bmp", (1800, 1800), "BMP"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("5 MB", r.context["form"].errors["foto"][0])
        self.assertFalse(FotoPerfil.objects.exists())

    def test_subir_otra_foto_reemplaza_y_borra_la_anterior(self):
        self.subir(imagen_prueba())
        anterior = FotoPerfil.objects.get(usuario=self.user).archivo.name
        self.subir(imagen_prueba(color="green"))
        self.assertEqual(FotoPerfil.objects.filter(usuario=self.user).count(), 1)
        nueva = FotoPerfil.objects.get(usuario=self.user).archivo.name
        self.assertNotEqual(anterior, nueva)
        self.assertTrue(default_storage.exists(nueva))
        self.assertFalse(default_storage.exists(anterior))

    def test_eliminar_borra_el_registro_y_el_archivo(self):
        self.subir(imagen_prueba())
        ruta = FotoPerfil.objects.get(usuario=self.user).archivo.name
        r = self.client.post(reverse("mi_perfil"), {"accion": "eliminar"})
        self.assertRedirects(r, reverse("mi_perfil"))
        self.assertFalse(FotoPerfil.objects.filter(usuario=self.user).exists())
        self.assertFalse(default_storage.exists(ruta))

    def test_la_vista_de_la_foto_devuelve_jpeg_o_404(self):
        url = reverse("foto_usuario", args=[self.user.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.subir(imagen_prueba())
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/jpeg")
        b"".join(r.streaming_content)

    def test_la_foto_exige_sesion(self):
        self.subir(imagen_prueba())
        self.client.logout()
        r = self.client.get(reverse("foto_usuario", args=[self.user.pk]))
        self.assertEqual(r.status_code, 302)