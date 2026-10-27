from flask import Blueprint, jsonify, current_app, session
from app.models.escola import Escola

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/versao-cache', methods=['GET'])
def versao_cache():
    """
    Retorna a versão do cache para controle do Service Worker (PWA).
    """
    return jsonify({
        "status": "online",
        "version": "1.0.0",
        "app_name": "Quadro de Aulas"
    })

@api_bp.route('/status-escola', methods=['GET'])
def status_escola():
    """
    Verifica o status da sessão ativa.
    """
    escola_id = session.get('escola_id')
    if not escola_id:
        return jsonify({"autenticado": False}), 401

    escola = Escola.query.get(escola_id)
    return jsonify({
        "autenticado": True,
        "codigo": escola.codigo,
        "nome": escola.nome
    })