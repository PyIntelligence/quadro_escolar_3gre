# app/routes/escolas.py

import os
import json
import time
import threading
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect, 
    url_for, flash, session, jsonify, Response, stream_with_context, current_app
)

from app.extensions import db

# --- Importação dos Modelos ---
try:
    from app.models.escola import Escola
except ImportError:
    try:
        from app.models.escola import EscolaGestao as Escola
    except ImportError:
        Escola = None

try:
    from app.models.professor import Professor
except ImportError:
    try:
        from app.models.profissional import Profissional as Professor
    except ImportError:
        Professor = None

try:
    from app.models.planejamento import Planejamento
except ImportError:
    Planejamento = None

from app.utils.import_siage import carregar_dados_siage

# Importação do sync_manager
try:
    from app.services.sync_manager import (
        executar_sincronizacao_completa, 
        PROGRESSO_ATUAL, 
        atualizar_progresso
    )
except Exception as e:
    import traceback
    PROGRESSO_ATUAL = {
        "percentual": 0, 
        "status": f"Erro de Módulo: {e}", 
        "em_execucao": False, 
        "erro": True
    }
    
    def atualizar_progresso(pct, msg, erro=False):
        PROGRESSO_ATUAL["percentual"] = pct
        PROGRESSO_ATUAL["status"] = msg
        PROGRESSO_ATUAL["erro"] = erro
        PROGRESSO_ATUAL["em_execucao"] = False

    def executar_sincronizacao_completa(url_google_sheets=None):
        atualizar_progresso(0, f"❌ Erro de importação: {e}", erro=True)

escolas_bp = Blueprint('escolas', __name__)


class EscolaView:
    """Wrapper universal de compatibilidade para renderização em templates Jinja2."""
    def __init__(self, e_id, inep, nome):
        self.id = e_id
        self.inep_visual = str(inep or '').strip()
        self.codigo_inep = str(inep or '').strip()
        self.inep = str(inep or '').strip()
        self.nome = nome or "ESCOLA"
        self.unidade_escolar = nome or "ESCOLA"


def resolver_escola_oficial(val):
    """
    Resolvedor Universal do PostgreSQL:
    Busca por INEP, ID Oficial, ID da tabela de Gestão Legada ou Profissional vinculado.
    """
    if not val:
        return None
    val_str = str(val).strip()
    if not val_str:
        return None
    val_clean = val_str.lstrip('0')

    # 1. Busca por INEP na tabela oficial 'escola'
    try:
        sql1 = db.text("""
            SELECT id, inep_visual, nome FROM escola 
            WHERE LTRIM(TRIM(CAST(inep_visual AS VARCHAR)), '0') = :clean
               OR TRIM(CAST(inep_visual AS VARCHAR)) = :raw
            LIMIT 1
        """)
        row = db.session.execute(sql1, {"clean": val_clean, "raw": val_str}).fetchone()
        if row:
            return row
    except Exception:
        db.session.rollback()

    # 2. Busca por ID numérico na tabela oficial 'escola'
    if val_str.isdigit():
        try:
            sql2 = db.text("SELECT id, inep_visual, nome FROM escola WHERE id = :eid LIMIT 1")
            row = db.session.execute(sql2, {"eid": int(val_str)}).fetchone()
            if row:
                return row
        except Exception:
            db.session.rollback()

    # 3. Busca por INEP ou ID na tabela legada 'escola_gestao' via JOIN
    try:
        sql3 = db.text("""
            SELECT e.id, e.inep_visual, e.nome 
            FROM escola e
            JOIN escola_gestao g 
              ON LTRIM(TRIM(CAST(g.codigo_inep AS VARCHAR)), '0') = LTRIM(TRIM(CAST(e.inep_visual AS VARCHAR)), '0')
            WHERE LTRIM(TRIM(CAST(g.codigo_inep AS VARCHAR)), '0') = :clean
               OR TRIM(CAST(g.codigo_inep AS VARCHAR)) = :raw
               OR g.id = :gid
            LIMIT 1
        """)
        gid = int(val_str) if val_str.isdigit() else -1
        row = db.session.execute(sql3, {"clean": val_clean, "raw": val_str, "gid": gid}).fetchone()
        if row:
            return row
    except Exception:
        db.session.rollback()

    # 4. Fallback direto na tabela 'escola_gestao'
    try:
        sql4 = db.text("""
            SELECT id, codigo_inep AS inep_visual, unidade_escolar AS nome 
            FROM escola_gestao 
            WHERE LTRIM(TRIM(CAST(codigo_inep AS VARCHAR)), '0') = :clean
               OR TRIM(CAST(codigo_inep AS VARCHAR)) = :raw
               OR id = :gid
            LIMIT 1
        """)
        gid = int(val_str) if val_str.isdigit() else -1
        row = db.session.execute(sql4, {"clean": val_clean, "raw": val_str, "gid": gid}).fetchone()
        if row:
            return row
    except Exception:
        db.session.rollback()

    return None


def obter_escola_atual():
    """Identifica e fixa a escola ativa sincronizando todas as chaves de sessão."""
    candidatos = [
        request.args.get('inep'),
        request.args.get('codigo_inep'),
        request.args.get('escola_id'),
        request.args.get('id'),
        request.form.get('codigo_inep_seletor'),
        request.form.get('selecionar_escola_id'),
        request.form.get('inep'),
        request.form.get('escola_id'),
        session.get('active_inep'),
        session.get('escola_inep'),
        session.get('codigo_inep'),
        session.get('inep'),
        session.get('escola_id'),
    ]

    row = None
    for cand in candidatos:
        if cand:
            row = resolver_escola_oficial(cand)
            if row:
                break

    if not row:
        try:
            row = db.session.execute(db.text("SELECT id, inep_visual, nome FROM escola ORDER BY id LIMIT 1")).fetchone()
        except Exception:
            db.session.rollback()

    if not row:
        try:
            row = db.session.execute(db.text("SELECT id, codigo_inep AS inep_visual, unidade_escolar AS nome FROM escola_gestao ORDER BY id LIMIT 1")).fetchone()
        except Exception:
            db.session.rollback()

    if not row:
        return None

    e_id, e_inep, e_nome = row[0], str(row[1] or '').strip(), str(row[2] or '').strip()

    session.permanent = True
    session['active_inep'] = e_inep
    session['escola_inep'] = e_inep
    session['codigo_inep'] = e_inep
    session['inep'] = e_inep
    session['inep_selecionado'] = e_inep
    session['escola_id'] = e_id
    session['id'] = e_id
    session['escola_nome'] = e_nome

    escola_obj = None
    if Escola:
        try:
            escola_obj = Escola.query.get(e_id)
        except Exception:
            db.session.rollback()

    if not escola_obj:
        escola_obj = EscolaView(e_id, e_inep, e_nome)

    return escola_obj


# --- HOME / LISTA GERAL DE ESCOLAS ---
@escolas_bp.route('/')
@escolas_bp.route('/escolas')
def index():
    try:
        escolas = Escola.query.order_by(Escola.id).all() if Escola else []
    except Exception:
        db.session.rollback()
        escolas = []

    total_escolas = len(escolas)
    escolas_confirmadas = sum(
        1 for e in escolas 
        if getattr(e, 'confirmado', False) or getattr(e, 'confirmacao_responsavel', '') == 'CONFIRMO AS INFORMAÇÕES'
    )

    return render_template(
        'index.html',
        escolas=escolas,
        total_escolas=total_escolas,
        escolas_confirmadas=escolas_confirmadas,
    )


# --- DADOS DA UNIDADE ESCOLAR ---
@escolas_bp.route('/escola', methods=['GET', 'POST'])
def escola():
    escola_obj = obter_escola_atual()

    if request.method == 'POST' and escola_obj:
        campos_ignorados = {'id', 'csrf_token', 'action', 'codigo_inep_seletor', 'escola_id', 'selecionar_escola_id'}
        
        form_tem_dados = any(k not in campos_ignorados for k in request.form)
        if form_tem_dados:
            for campo in request.form:
                if campo not in campos_ignorados and hasattr(escola_obj, campo):
                    setattr(escola_obj, campo, request.form.get(campo))

            try:
                db.session.commit()
                flash('Dados salvos com sucesso!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao salvar os dados: {str(e)}', 'danger')

        active_inep = session.get('active_inep', '')
        return redirect(url_for('escolas.escola', inep=active_inep))

    todas_escolas = []
    try:
        sql_todas = db.text("SELECT id, inep_visual, nome FROM escola ORDER BY nome")
        rows_todas = db.session.execute(sql_todas).fetchall()
        todas_escolas = [EscolaView(r[0], r[1], r[2]) for r in rows_todas]
    except Exception:
        db.session.rollback()

    inep_selecionado = session.get('active_inep', '')

    return render_template(
        'escola.html',
        registro=escola_obj,
        escola=escola_obj,
        todas_escolas=todas_escolas,
        inep_selecionado=inep_selecionado
    )


# --- ROTA DE AUTOSAVE ---
@escolas_bp.route('/autosave_escola', methods=['POST'])
def autosave_escola():
    data = request.get_json(silent=True) or {}
    codigo_inep = data.get('codigo_inep')
    campo = data.get('campo')
    valor = data.get('valor')

    if not codigo_inep or not campo or not Escola:
        return jsonify({"status": "erro", "mensagem": "Dados inválidos"}), 400

    try:
        inep_clean = str(codigo_inep).strip().lstrip('0')
        sql = db.text("SELECT id FROM escola WHERE LTRIM(TRIM(CAST(inep_visual AS VARCHAR)), '0') = :inep LIMIT 1")
        res = db.session.execute(sql, {"inep": inep_clean}).fetchone()
        
        escola_obj = Escola.query.get(res[0]) if res else None

        if escola_obj and hasattr(escola_obj, campo):
            setattr(escola_obj, campo, valor)
            if hasattr(escola_obj, 'ultima_atualizacao'):
                escola_obj.ultima_atualizacao = datetime.now()
            db.session.commit()
            
            data_formatada = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            return jsonify({"status": "sucesso", "ultima_atualizacao": data_formatada})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

    return jsonify({"status": "erro", "mensagem": "Escola não encontrada"}), 404


# Sincronização SIAGE / Playwright
try:
    from extrair_siage_playwright import (
        obter_escolas_da_gre,
        sincronizar_escolas_no_postgres,
        extrair_profissionais_por_escolas,
        salvar_professores_no_postgres,
        DADOS_SESSAO,
        extrair_token_do_local_storage
    )
except ImportError:
    pass

@escolas_bp.route('/sincronizar_siage', methods=['GET', 'POST'])
def sincronizar_siage():
    if request.method == 'POST':
        try:
            from playwright.sync_api import sync_playwright
            import os

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                NOME_ARQUIVO_SESSAO = "sessao_siage.json"
                
                if os.path.exists(NOME_ARQUIVO_SESSAO):
                    context = browser.new_context(storage_state=NOME_ARQUIVO_SESSAO)
                else:
                    context = browser.new_context()

                page = context.new_page()
                page.goto("https://escola.see.pb.gov.br", wait_until="domcontentloaded")
                
                token = extrair_token_do_local_storage(page)
                if token:
                    DADOS_SESSAO["token"] = token
                
                escolas_api = obter_escolas_da_gre(page)
                if escolas_api:
                    mapa_escolas = sincronizar_escolas_no_postgres(escolas_api)
                    profissionais = extrair_profissionais_por_escolas(page, escolas_api)
                    salvar_professores_no_postgres(profissionais, mapa_escolas)

                browser.close()

            flash("✅ Sincronização Inteligente concluída com sucesso no banco de dados!", "success")
            return redirect(url_for('professores.professores'))

        except Exception as e:
            flash(f"❌ Erro durante a sincronização: {str(e)}", "danger")
            return redirect(url_for('escolas.sincronizar_siage'))

    return render_template('sincronizar_siage.html')


def _tarefa_sincronizacao_bg(app, url_sheets):
    with app.app_context():
        try:
            executar_sincronizacao_completa(url_google_sheets=url_sheets)
        except Exception as e:
            atualizar_progresso(0, f"❌ Erro na execução: {str(e)}", erro=True)


@escolas_bp.route('/executar_sincronizacao_siage', methods=['POST'])
def executar_sincronizacao_siage():
    if PROGRESSO_ATUAL.get("em_execucao"):
        return jsonify({"status": "erro", "mensagem": "Já existe uma sincronização em andamento."}), 400

    data = request.get_json(silent=True) or {}
    url_sheets = data.get('url_google_sheets') or request.form.get('url_google_sheets')

    atualizar_progresso(1, "🚀 Iniciando conexão com o servidor do SIAGE...")
    app = current_app._get_current_object()
    thread = threading.Thread(target=_tarefa_sincronizacao_bg, args=(app, url_sheets))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "sucesso", "mensagem": "Robô inteligente de sincronização iniciado."})


@escolas_bp.route('/stream_progresso_siage', methods=['GET'])
def stream_progresso_siage():
    def gerar_eventos():
        while True:
            data_str = json.dumps(PROGRESSO_ATUAL)
            yield f"data: {data_str}\n\n"
            if not PROGRESSO_ATUAL.get("em_execucao"):
                break
            time.sleep(0.8)

    return Response(stream_with_context(gerar_eventos()), mimetype='text/event-stream')


# @escolas_bp.route('/atuacao', methods=['GET', 'POST'])
# def atuacao():
#     escola_obj = obter_escola_atual()
#     return render_template('atuacao.html', escola=escola_obj, registro=escola_obj)


# @escolas_bp.route('/quadro_informado', methods=['GET', 'POST'])
# def quadro_informado():
#     escola_obj = obter_escola_atual()
#     return render_template('quadro_informado.html', escola=escola_obj, registro=escola_obj)


# @escolas_bp.route('/quadro_escolar', methods=['GET', 'POST'])
# def quadro_escolar():
#     escola_obj = obter_escola_atual()
#     return render_template('quadro_escolar.html', escola=escola_obj, registro=escola_obj)


# @escolas_bp.route('/conferencia_final', methods=['GET', 'POST'])
# def conferencia_final():
#     escola_obj = obter_escola_atual()
#     total_profs = len(escola_obj.professores) if escola_obj and hasattr(escola_obj, 'professores') else 0
#     indicadores = {
#         'total_professores': total_profs,
#         'saldo_ch_geral': 0.0,
#         'ch_necessaria': 0.0,
#         'ch_atendida': 0.0,
#         'diferenca_ch': 0.0,
#     }
#     return render_template('conferencia_final.html', escola=escola_obj, registro=escola_obj, indicadores=indicadores)


# @escolas_bp.route('/confirmacao_final', methods=['GET', 'POST'])
# def confirmacao_final():
#     escola_obj = obter_escola_atual()
#     total_profs = len(escola_obj.professores) if escola_obj and hasattr(escola_obj, 'professores') else 0
#     resumo = {
#         'total_professores': total_profs,
#         'saldo_ch_geral': 0.0,
#         'ch_necessaria': 0.0,
#         'ch_atendida': 0.0,
#     }
#     return render_template('confirmacao_final.html', escola=escola_obj, registro=escola_obj, resumo=resumo)