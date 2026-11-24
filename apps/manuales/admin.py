from django.contrib import admin

from .models import CategoriaManual, Manual


@admin.register(CategoriaManual)
class CategoriaManualAdmin(admin.ModelAdmin):
    list_display = ("nombre", "manuales", "creada_en")
    search_fields = ("nombre",)

    @admin.display(description="Manuales")
    def manuales(self, obj):
        return Manual.objects.filter(categoria=obj.nombre).count()

    def save_model(self, request, obj, form, change):
        if change and "nombre" in form.changed_data:
            anterior = form.initial.get("nombre")
            super().save_model(request, obj, form, change)
            if anterior:
                Manual.objects.filter(categoria=anterior).update(categoria=obj.nombre)
            return
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and Manual.objects.filter(categoria=obj.nombre).exists():
            return False
        return super().has_delete_permission(request, obj)