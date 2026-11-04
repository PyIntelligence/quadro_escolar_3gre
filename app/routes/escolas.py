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
    def __init__(self, e_id=None, inep="", nome="", municipio="", modalidade="", endereco="", zona="", email="", telefone="", gestor="", qtd_professores=0, competencia="AGOSTO/2026", confirmacao_responsavel="CONFIRMO AS INFORMAÇÕES", ultima_atualizacao=None, turnos_funcionamento="INTEGRAL", responsavel_preenchimento="", cargo_funcao="", ute="0000", **kwargs):
        self.id = e_id
        self.inep_visual = str(inep or '').strip()
        self.codigo_inep = str(inep or '').strip()
        self.inep = str(inep or '').strip()
        self.nome = nome or "ESCOLA"
        self.unidade_escolar = nome or "ESCOLA"

        # Função interna para higienizar marcações 'EMPTY_STRING' e 'NULL'
        def limpar_campo(val, padrao=""):
            if val is None:
                return padrao
            s = str(val).strip()
            if s.upper() in ('EMPTY_STRING', 'NONE', 'NULL', 'RUA, Nº, BAIRRO', '(83) 90000-0000', 'ESCOLA@EDUCACAO.PB.GOV.BR'):
                return padrao
            return s

        self.municipio = limpar_campo(municipio, "CAMPINA GRANDE")
        self.modalidade = limpar_campo(modalidade, "")
        self.endereco = limpar_campo(endereco, "")
        self.zona = limpar_campo(zona, "URBANA")
        self.email = limpar_campo(email, "")
        self.telefone = limpar_campo(telefone, "")
        self.gestor = limpar_campo(gestor, "")
        self.ute = limpar_campo(ute, "0000")
        self.turnos_funcionamento = limpar_campo(turnos_funcionamento, "INTEGRAL")
        self.responsavel_preenchimento = limpar_campo(responsavel_preenchimento, "")
        self.cargo_funcao = limpar_campo(cargo_funcao, "")
        
        self.qtd_professores = qtd_professores or 0
        self.competencia = competencia or "AGOSTO/2026"
        self.confirmacao_responsavel = confirmacao_responsavel or "CONFIRMO AS INFORMAÇÕES"
        self.ultima_atualizacao = ultima_atualizacao

        # Atribuição segura de atributos extras sem duplicidade
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, limpar_campo(v) if isinstance(v, str) else v)


def resolver_escola_completa(val):
    """
    Busca e unifica os dados das tabelas 'escola' e 'escola_gestao',
    coletando todos os IDs e INEPs vinculados para cruzamento perfeito.
    """
    if not val:
        return None, [], []
    val_str = str(val).strip()
    if not val_str:
        return None, [], []
    val_clean = val_str.lstrip('0')
    gid = int(val_str) if val_str.isdigit() else -1

    dados = {}
    ids_encontrados = set()
    ineps_encontrados = set()

    if val_str:
        ineps_encontrados.add(val_str)
        ineps_encontrados.add(val_clean)
    if gid > 0:
        ids_encontrados.add(gid)

    # 1. Busca na tabela 'escola'
    try:
        sql1 = db.text("""
            SELECT * FROM escola 
            WHERE LTRIM(TRIM(CAST(inep_visual AS VARCHAR)), '0') = :clean
               OR TRIM(CAST(inep_visual AS VARCHAR)) = :raw
               OR id = :gid
            LIMIT 1
        """)
        r1 = db.session.execute(sql1, {"clean": val_clean, "raw": val_str, "gid": gid}).fetchone()
        if r1:
            d1 = dict(r1._mapping) if hasattr(r1, '_mapping') else {}
            dados.update(d1)
            if d1.get('id'):
                ids_encontrados.add(d1['id'])
            inep_v = str(d1.get('inep_visual') or d1.get('codigo_inep') or '').strip()
            if inep_v:
                ineps_encontrados.add(inep_v)
                ineps_encontrados.add(inep_v.lstrip('0'))
    except Exception:
        db.session.rollback()

    # 2. Busca na tabela 'escola_gestao'
    try:
        sql2 = db.text("""
            SELECT * FROM escola_gestao 
            WHERE LTRIM(TRIM(CAST(codigo_inep AS VARCHAR)), '0') = :clean
               OR TRIM(CAST(codigo_inep AS VARCHAR)) = :raw
               OR id = :gid
            LIMIT 1
        """)
        r2 = db.session.execute(sql2, {"clean": val_clean, "raw": val_str, "gid": gid}).fetchone()
        if r2:
            d2 = dict(r2._mapping) if hasattr(r2, '_mapping') else {}
            if d2.get('id'):
                ids_encontrados.add(d2['id'])
            inep_g = str(d2.get('codigo_inep') or d2.get('inep_visual') or '').strip()
            if inep_g:
                ineps_encontrados.add(inep_g)
                ineps_encontrados.add(inep_g.lstrip('0'))
            
            for k, v in d2.items():
                v_str = str(v).strip().upper() if v else ''
                if k not in dados or not dados[k] or v_str in ['NONE', 'NULL', 'EMPTY_STRING', '']:
                    dados[k] = v
    except Exception:
        db.session.rollback()

    # Mapeamento de sinônimos
    if not dados.get('municipio') or str(dados.get('municipio')).strip().upper() == 'EMPTY_STRING':
        dados['municipio'] = dados.get('cidade') or dados.get('nome_municipio') or 'CAMPINA GRANDE'
    if not dados.get('endereco') or str(dados.get('endereco')).strip().upper() == 'EMPTY_STRING':
        dados['endereco'] = dados.get('logradouro') or ''
    if not dados.get('gestor') or str(dados.get('gestor')).strip().upper() == 'EMPTY_STRING':
        dados['gestor'] = dados.get('diretor') or dados.get('nome_gestor') or ''
    if not dados.get('telefone') or str(dados.get('telefone')).strip().upper() == 'EMPTY_STRING':
        dados['telefone'] = dados.get('fone') or dados.get('num_telefone') or ''
    if not dados.get('email') or str(dados.get('email')).strip().upper() == 'EMPTY_STRING':
        dados['email'] = dados.get('email_institucional') or ''

    return (dados if dados else None), list(ids_encontrados), list(ineps_encontrados)


def contar_professores_escola(ids_list, ineps_list):
    """Calcula o total real de professores vinculados consultando todas as tabelas."""
    if not ids_list and not ineps_list:
        return 0
        
    clean_ineps = tuple(set([str(x).strip().lstrip('0') for x in ineps_list if x]) or ['___none___'])
    ids_tuple = tuple([int(x) for x in ids_list if str(x).isdigit()] or [-1])

    total = 0

    try:
        sql_p = db.text("""
            SELECT COUNT(DISTINCT id) FROM professores 
            WHERE escola_id IN :ids 
               OR LTRIM(TRIM(CAST(COALESCE(escola_inep, codigo_inep, inep, '') AS VARCHAR)), '0') IN :cleans
        """)
        res = db.session.execute(sql_p, {"ids": ids_tuple, "cleans": clean_ineps}).scalar()
        if res and res > 0:
            total = max(total, res)
    except Exception:
        db.session.rollback()

    try:
        sql_p2 = db.text("""
            SELECT COUNT(DISTINCT id) FROM professor 
            WHERE escola_id IN :ids 
               OR LTRIM(TRIM(CAST(COALESCE(escola_inep, codigo_inep, inep, '') AS VARCHAR)), '0') IN :cleans
        """)
        res2 = db.session.execute(sql_p2, {"ids": ids_tuple, "cleans": clean_ineps}).scalar()
        if res2 and res2 > 0:
            total = max(total, res2)
    except Exception:
        db.session.rollback()

    try:
        sql_a = db.text("""
            SELECT COUNT(DISTINCT COALESCE(professor_id, professor_cpf, professor_nome)) FROM atuacao 
            WHERE escola_id IN :ids 
               OR LTRIM(TRIM(CAST(COALESCE(codigo_inep, inep, '') AS VARCHAR)), '0') IN :cleans
        """)
        res3 = db.session.execute(sql_a, {"ids": ids_tuple, "cleans": clean_ineps}).scalar()
        if res3 and res3 > 0:
            total = max(total, res3)
    except Exception:
        db.session.rollback()

    return total


def obter_escola_atual():
    """Identifica a escola ativa e calcula a quantidade real de professores."""
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

    dados_escola = None
    ids_lista, ineps_lista = [], []

    for cand in candidatos:
        if cand:
            dados_escola, ids_lista, ineps_lista = resolver_escola_completa(cand)
            if dados_escola:
                break

    if not dados_escola:
        try:
            r = db.session.execute(db.text("SELECT * FROM escola ORDER BY id LIMIT 1")).fetchone()
            if r:
                dados_escola = dict(r._mapping) if hasattr(r, '_mapping') else {}
                ids_lista = [dados_escola.get('id')] if dados_escola.get('id') else []
                ineps_lista = [dados_escola.get('inep_visual')] if dados_escola.get('inep_visual') else []
        except Exception:
            db.session.rollback()

    if not dados_escola:
        return None

    e_id = dados_escola.get('id')
    e_inep = str(dados_escola.get('inep_visual') or dados_escola.get('codigo_inep') or dados_escola.get('inep') or '').strip()
    e_nome = str(dados_escola.get('nome') or dados_escola.get('unidade_escolar') or '').strip()

    total_professores = contar_professores_escola(ids_lista, ineps_lista)

    session.permanent = True
    session['active_inep'] = e_inep
    session['escola_inep'] = e_inep
    session['codigo_inep'] = e_inep
    session['inep'] = e_inep
    session['inep_selecionado'] = e_inep
    session['escola_id'] = e_id
    session['id'] = e_id
    session['escola_nome'] = e_nome

    chaves_explicitas = {
        'id', 'inep', 'inep_visual', 'codigo_inep', 'nome', 'unidade_escolar',
        'municipio', 'modalidade', 'endereco', 'zona', 'email', 'telefone',
        'gestor', 'qtd_professores', 'competencia', 'confirmacao_responsavel',
        'ultima_atualizacao', 'turnos_funcionamento', 'responsavel_preenchimento',
        'cargo_funcao', 'ute'
    }
    extra_kwargs = {k: v for k, v in dados_escola.items() if k not in chaves_explicitas}

    escola_obj = EscolaView(
        e_id=e_id,
        inep=e_inep,
        nome=e_nome,
        municipio=dados_escola.get('municipio', 'CAMPINA GRANDE'),
        modalidade=dados_escola.get('modalidade', ''),
        endereco=dados_escola.get('endereco', ''),
        zona=dados_escola.get('zona', 'URBANA'),
        email=dados_escola.get('email', ''),
        telefone=dados_escola.get('telefone', ''),
        gestor=dados_escola.get('gestor', ''),
        ute=dados_escola.get('ute', '0000'),
        qtd_professores=total_professores,
        turnos_funcionamento=dados_escola.get('turnos_funcionamento', 'INTEGRAL'),
        responsavel_preenchimento=dados_escola.get('responsavel_preenchimento', ''),
        cargo_funcao=dados_escola.get('cargo_funcao', ''),
        competencia=dados_escola.get('competencia', 'AGOSTO/2026'),
        confirmacao_responsavel=dados_escola.get('confirmacao_responsavel', 'CONFIRMO AS INFORMAÇÕES'),
        ultima_atualizacao=dados_escola.get('ultima_atualizacao'),
        **extra_kwargs
    )

    return escola_obj


def salvar_dados_escola_banco(inep_or_id, form_data):
    """Salva as alterações em ambas as tabelas 'escola' e 'escola_gestao'."""
    if not inep_or_id:
        return
    clean = str(inep_or_id).strip().lstrip('0')
    raw = str(inep_or_id).strip()
    gid = int(raw) if raw.isdigit() else -1

    campos_ignorados = {'id', 'csrf_token', 'action', 'codigo_inep_seletor', 'escola_id', 'selecionar_escola_id'}

    for campo, valor in form_data.items():
        if campo in campos_ignorados:
            continue
        
        try:
            sql_e = db.text(f"""
                UPDATE escola 
                SET {campo} = :val, ultima_atualizacao = NOW()
                WHERE LTRIM(TRIM(CAST(inep_visual AS VARCHAR)), '0') = :clean
                   OR TRIM(CAST(inep_visual AS VARCHAR)) = :raw
                   OR id = :gid
            """)
            db.session.execute(sql_e, {"val": valor, "clean": clean, "raw": raw, "gid": gid})
        except Exception:
            db.session.rollback()

        try:
            sql_g = db.text(f"""
                UPDATE escola_gestao 
                SET {campo} = :val, ultima_atualizacao = NOW()
                WHERE LTRIM(TRIM(CAST(codigo_inep AS VARCHAR)), '0') = :clean
                   OR TRIM(CAST(codigo_inep AS VARCHAR)) = :raw
                   OR id = :gid
            """)
            db.session.execute(sql_g, {"val": valor, "clean": clean, "raw": raw, "gid": gid})
        except Exception:
            db.session.rollback()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


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
        salvar_dados_escola_banco(escola_obj.codigo_inep or escola_obj.id, request.form)
        flash('Dados salvos com sucesso!', 'success')
        active_inep = session.get('active_inep', '')
        return redirect(url_for('escolas.escola', inep=active_inep))

    todas_escolas = []
    try:
        sql_todas = db.text("SELECT * FROM escola ORDER BY nome")
        rows_todas = db.session.execute(sql_todas).fetchall()
        chaves_explicitas = {
            'id', 'inep', 'inep_visual', 'codigo_inep', 'nome', 'unidade_escolar',
            'municipio', 'modalidade', 'endereco', 'zona', 'email', 'telefone',
            'gestor', 'qtd_professores', 'competencia', 'confirmacao_responsavel',
            'ultima_atualizacao', 'turnos_funcionamento', 'responsavel_preenchimento',
            'cargo_funcao', 'ute'
        }
        for r in rows_todas:
            d = dict(r._mapping) if hasattr(r, '_mapping') else {}
            extra_d = {k: v for k, v in d.items() if k not in chaves_explicitas}
            todas_escolas.append(EscolaView(
                e_id=d.get('id'),
                inep=str(d.get('inep_visual') or d.get('codigo_inep') or '').strip(),
                nome=str(d.get('nome') or d.get('unidade_escolar') or '').strip(),
                municipio=d.get('municipio', 'CAMPINA GRANDE'),
                modalidade=d.get('modalidade', ''),
                endereco=d.get('endereco', ''),
                zona=d.get('zona', 'URBANA'),
                email=d.get('email', ''),
                telefone=d.get('telefone', ''),
                gestor=d.get('gestor', ''),
                ute=d.get('ute', '0000'),
                **extra_d
            ))
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

    if not codigo_inep or not campo:
        return jsonify({"status": "erro", "mensagem": "Dados inválidos"}), 400

    salvar_dados_escola_banco(codigo_inep, {campo: valor})
    data_formatada = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    return jsonify({"status": "sucesso", "ultima_atualizacao": data_formatada})


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