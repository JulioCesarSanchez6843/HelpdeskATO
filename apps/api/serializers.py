from rest_framework import serializers

from apps.accounts.models import Usuario
from apps.tickets.models import AdjuntoTicket, Comentario, Historial, Ticket


class UsuarioSerializer(serializers.ModelSerializer):
    sucursal = serializers.StringRelatedField()
    area = serializers.StringRelatedField()
    puesto = serializers.StringRelatedField()

    class Meta:
        model = Usuario
        fields = [
            "id", "nombre", "correo", "rol",
            "sucursal", "area", "puesto", "debe_cambiar_password",
        ]


class ComentarioSerializer(serializers.ModelSerializer):
    autor = serializers.SerializerMethodField()

    class Meta:
        model = Comentario
        fields = ["id", "autor", "contenido", "interno", "creado_en"]

    def get_autor(self, comentario):
        return comentario.autor.nombre


class HistorialSerializer(serializers.ModelSerializer):
    usuario = serializers.SerializerMethodField()
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = Historial
        fields = ["id", "tipo", "tipo_display", "usuario", "contenido", "fecha"]

    def get_usuario(self, historial):
        return historial.usuario.nombre


class AdjuntoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdjuntoTicket
        fields = ["id", "nombre", "tipo_contenido", "tamano", "subido_en"]


class TicketListSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    prioridad_display = serializers.CharField(
        source="get_prioridad_display", read_only=True
    )
    categoria = serializers.StringRelatedField()
    sucursal = serializers.StringRelatedField()
    creado_por = serializers.SerializerMethodField()
    asignado_a = serializers.SerializerMethodField()
    sla_vencido = serializers.BooleanField(read_only=True)
    asignado_a_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id", "titulo", "estado", "estado_display", "asignado_a_id",
            "prioridad", "prioridad_display", "categoria", "sucursal",
            "creado_por", "asignado_a", "creado_en",
            "sla_vence_en", "sla_vencido",
        ]

    def get_creado_por(self, ticket):
        return ticket.creado_por.nombre

    def get_asignado_a(self, ticket):
        return ticket.asignado_a.nombre if ticket.asignado_a else None


class TicketDetalleSerializer(TicketListSerializer):
    area = serializers.StringRelatedField()
    comentarios = serializers.SerializerMethodField()
    historial = serializers.SerializerMethodField()
    adjuntos = serializers.SerializerMethodField()
    permisos = serializers.SerializerMethodField()

    class Meta(TicketListSerializer.Meta):
        fields = TicketListSerializer.Meta.fields + [
            "descripcion", "numero_serie", "area", "nota_resolucion",
            "cerrado_en", "comentarios", "historial", "adjuntos", "permisos",
        ]

    def get_comentarios(self, ticket):
        comentarios = ticket.comentarios.select_related("autor")
        if not self.context["request"].user.es_personal:
            comentarios = comentarios.filter(interno=False)
        return ComentarioSerializer(comentarios, many=True).data

    def get_historial(self, ticket):
        eventos = ticket.historial.select_related("usuario")
        if not self.context["request"].user.es_personal:
            eventos = eventos.exclude(tipo=Historial.Tipo.ESCALADO)
        return HistorialSerializer(eventos, many=True).data

    def get_adjuntos(self, ticket):
        return AdjuntoSerializer(ticket.adjuntos.filter(comentario__isnull=True), many=True).data

    def get_permisos(self, ticket):
        usuario = self.context["request"].user
        abierto = ticket.estado != Ticket.Estado.CERRADO
        return {
            "puede_comentar": abierto,
            "puede_tomar": (
                usuario.es_personal
                and not usuario.es_superadmin
                and ticket.asignado_a_id is None
                and abierto
                and usuario.sucursal_id == ticket.sucursal_id
            ),
            "puede_asignar": usuario.es_admin,
            "puede_reabrir": ticket.dentro_de_plazo_reapertura,
            "puede_responder_cierre": (
                ticket.esperando_confirmacion
                and ticket.creado_por_id == usuario.pk
            ),
        }