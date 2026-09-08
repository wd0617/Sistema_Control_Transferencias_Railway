from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app.models.cliente import Servicio
from app.utils.tenancy import query_negocio
from datetime import datetime

calculadora = Blueprint('calculadora', __name__)

@calculadora.route('/')
@login_required
def index():
    servicios = query_negocio(Servicio).filter_by(activo=True).all()
    return render_template('calculadora/index.html', servicios=servicios, now=datetime.now())

@calculadora.route('/calcular', methods=['POST'])
@login_required
def calcular():
    try:
        monto = float(request.form.get('monto', 0))
        servicio_id = int(request.form.get('servicio_id', 0))
        
        servicio = query_negocio(Servicio).filter_by(id=servicio_id).first()
        if not servicio:
            return jsonify({
                'success': False,
                'message': 'Servicio no encontrado'
            })
        
        comision = (monto * servicio.comision_porcentaje) / 100
        total = monto + comision
        
        return jsonify({
            'success': True,
            'data': {
                'monto': monto,
                'comision_porcentaje': servicio.comision_porcentaje,
                'comision': comision,
                'total': total
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error en el cálculo: {str(e)}'
        })
