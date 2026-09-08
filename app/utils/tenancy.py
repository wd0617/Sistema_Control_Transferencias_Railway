"""Utilidades de multitenancy: aislamiento de datos por negocio.

Regla de oro: toda consulta sobre modelos con `negocio_id` debe pasar por
`query_negocio(...)` o filtrar explícitamente por `current_negocio_id()`.
El listener `before_insert` registrado en `registrar_listener_tenancy`
estampa el negocio automáticamente al crear registros.
"""
from flask import session
from flask_login import current_user


def current_negocio_id():
    """Devuelve el negocio activo para la petición actual.

    - Usuario normal: su propio `negocio_id`.
    - Superadmin en modo soporte: el negocio guardado en sesión.
    - Superadmin sin modo soporte / sin autenticar: None (ver todo; solo
      deben usarlo los paneles de administración).
    """
    if not current_user or not current_user.is_authenticated:
        return None
    if current_user.is_superadmin:
        return session.get('negocio_vista')
    return current_user.negocio_id


def negocio_vista_actual():
    """Negocio que el superadmin está viendo en modo soporte (o None)."""
    if not current_user or not current_user.is_authenticated or not current_user.is_superadmin:
        return None
    negocio_id = session.get('negocio_vista')
    if not negocio_id:
        return None
    from app.models.negocio import Negocio
    return Negocio.query.get(negocio_id)


def query_negocio(modelo):
    """Atajo: `modelo.query` filtrado por el negocio actual.

    Si `current_negocio_id()` es None (superadmin sin modo soporte),
    devuelve la consulta sin filtrar.
    """
    negocio_id = current_negocio_id()
    if negocio_id is None:
        return modelo.query
    return modelo.query.filter(modelo.negocio_id == negocio_id)


def get_negocio_o_404(modelo, id):
    """`get_or_404` que además exige que el registro sea del negocio actual."""
    from flask import abort
    obj = modelo.query.get(id)
    if obj is None:
        abort(404)
    negocio_id = current_negocio_id()
    if negocio_id is not None and obj.negocio_id != negocio_id:
        abort(404)
    return obj


def registrar_listener_tenancy():
    """Registra listeners que estampan `negocio_id` al insertar registros.

    Solo aplica si el objeto no trae ya un negocio asignado. Fuera de
    contexto de petición (scripts, seeds) no hace nada.
    """
    from sqlalchemy import event
    from app.models.cliente import Cliente, Servicio
    from app.models.transaccion import Transaccion, Notificacion
    from app.models.documento import DocumentoCliente
    from app.models.producto import Producto, MovimientoProducto
    from app.models.caja import CajaSesion, MovimientoCaja

    modelos_tenant = (Cliente, Servicio, Transaccion, Notificacion,
                      DocumentoCliente, Producto, MovimientoProducto,
                      CajaSesion, MovimientoCaja)

    def _estampar_negocio(mapper, connection, target):
        if target.negocio_id is not None:
            return
        try:
            negocio_id = current_negocio_id()
        except Exception:
            return  # Sin contexto de request (scripts): no estampar
        if negocio_id is not None:
            target.negocio_id = negocio_id

    for modelo in modelos_tenant:
        event.listen(modelo, 'before_insert', _estampar_negocio)
