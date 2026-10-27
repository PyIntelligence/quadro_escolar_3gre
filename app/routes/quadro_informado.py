# app/routes/quadro_informado.py

from flask import Blueprint, render_template, request, session
from app.extensions import db
from app.models.professor import Professor

quadro_informado_bp = Blueprint('quadro_informado', __name__)


class EscolaView:
    """Wrapper para passagem segura de atributos de escola ao Jinja2."""
    def __init__(self, e_id, inep, nome):
        self.id = e_id
        self.inep_visual = str(inep or '').strip()
        self.codigo_inep = str(inep or '').strip()
        self.inep = str(inep or '').strip()
        self.nome = nome or "ESCOLA"
        self.unidade_escolar = nome or "ESCOLA"

    def __getattr__(self, name):
        return ""


@quadro_informado_bp.route('/quadro_informado', methods=['GET'])
def quadro_informado():
    # 1. Pega identificadores na URL ou na Sessão
    inep_req = (
        request.args.get('inep') or 
        request.args.get('codigo_inep') or 
        request.args.get('escola_id') or 
        request.args.get('id')
    )

    inep_sessao = (
        session.get('active_inep') or
        session.get('escola_inep') or 
        session.get('codigo_inep') or 
        session.get('inep') or 
        session.get('inep_selecionado') or
        session.get('escola_id')
    )

    escola_row = None
    alvo = inep_req or inep_sessao

    if alvo:
        val_str = str(alvo).strip()
        val_clean = val_str.lstrip('0')
        try:
            sql = db.text("""
                SELECT id, inep_visual, nome 
                FROM escola 
                WHERE LTRIM(TRIM(CAST(inep_visual AS VARCHAR)), '0') = :clean
                   OR TRIM(CAST(inep_visual AS VARCHAR)) = :raw
                   OR CAST(id AS VARCHAR) = :raw
                LIMIT 1
            """)
            escola_row = db.session.execute(sql, {"clean": val_clean, "raw": val_str}).fetchone()
        except Exception as e:
            db.session.rollback()

    if not escola_row:
        try:
            sql_f = db.text("SELECT id, inep_visual, nome FROM escola ORDER BY id LIMIT 1")
            escola_row = db.session.execute(sql_f).fetchone()
        except Exception as e:
            db.session.rollback()

    if escola_row:
        e_id, e_inep, e_nome = escola_row[0], str(escola_row[1] or '').strip(), str(escola_row[2] or '').strip()
    else:
        e_id, e_inep, e_nome = None, "", "ESCOLA"

    if e_inep:
        session.permanent = True
        session['active_inep'] = e_inep
        session['escola_inep'] = e_inep
        session['codigo_inep'] = e_inep
        session['inep'] = e_inep
        session['inep_selecionado'] = e_inep
        session['escola_id'] = e_id
        session['id'] = e_id
        session['escola_nome'] = e_nome

    escola_ativa = EscolaView(e_id, e_inep, e_nome)

    # 2. Carrega os professores da escola no PostgreSQL
    professores = []
    if e_id or e_inep:
        clean_inep = e_inep.lstrip('0')
        try:
            sql_profs = db.text("""
                SELECT p.id 
                FROM professores p
                WHERE p.escola_id = :eid 
                   OR LTRIM(TRIM(CAST(p.escola_inep AS VARCHAR)), '0') = :inep
                   OR p.escola_id IN (
                       SELECT id FROM escola 
                       WHERE LTRIM(TRIM(CAST(inep_visual AS VARCHAR)), '0') = :inep
                   )
                ORDER BY p.nome
            """)
            p_ids = [r[0] for r in db.session.execute(sql_profs, {"eid": e_id, "inep": clean_inep}).fetchall()]
            if p_ids:
                professores = Professor.query.filter(Professor.id.in_(p_ids)).order_by(Professor.nome).all()
            print(f"\n[DIAGNÓSTICO QUADRO INFORMADO] Encontrados {len(professores)} professores para escola_id {e_id} (INEP {e_inep})\n")
        except Exception as e:
            print(f"[ERRO QUADRO INFORMADO - PROFESSORES]: {e}")
            db.session.rollback()

    # 3. Carrega as atuações/disciplinas usando a chave escola_id do PostgreSQL
    atuacoes_por_prof = {}
    if e_id or e_inep:
        clean_inep = e_inep.lstrip('0')
        try:
            sql_atuacoes = db.text("""
                SELECT matricula, professor_nome, atividade_componente, ch_semanal
                FROM atuacao
                WHERE escola_id = :eid 
                   OR escola_id IN (
                       SELECT id FROM escola 
                       WHERE LTRIM(TRIM(CAST(inep_visual AS VARCHAR)), '0') = :inep
                   )
            """)
            rows_at = db.session.execute(sql_atuacoes, {"eid": e_id, "inep": clean_inep}).fetchall()
            for row in rows_at:
                mat = str(row[0] or '').strip().upper()
                p_nome = str(row[1] or '').strip().upper()
                comp = str(row[2] or 'COMPONENTE CURRICULAR').strip()
                ch = float(row[3] or 0.0)
                
                item = {"componente": comp, "ch": ch}
                if mat:
                    atuacoes_por_prof.setdefault(mat, []).append(item)
                if p_nome:
                    atuacoes_por_prof.setdefault(p_nome, []).append(item)
        except Exception as e:
            print(f"[AVISO QUADRO INFORMADO - ATUACAO]: {e}")
            db.session.rollback()

    # 4. Preenche a lista do dropdown de escolas
    todas_escolas = []
    try:
        sql_todas = db.text("SELECT id, inep_visual, nome FROM escola ORDER BY nome")
        rows_todas = db.session.execute(sql_todas).fetchall()
        todas_escolas = [EscolaView(r[0], r[1], r[2]) for r in rows_todas]
    except Exception as e:
        print(f"[ERRO QUADRO INFORMADO - TODAS ESCOLAS]: {e}")
        db.session.rollback()

    # 5. Consolida os dados no modelo oficial das 9 colunas
    dados_consolidados = []
    total_ch_autorizada = 0
    total_ch_alocada = 0
    qtd_incompletos = 0
    qtd_excesso = 0

    for p in professores:
        p_mat = str(getattr(p, 'matricula', '') or '').strip().upper()
        p_nome = str(getattr(p, 'nome', '') or '').strip().upper()

        list_at = atuacoes_por_prof.get(p_mat) or atuacoes_por_prof.get(p_nome) or []
        
        comp_lista = []
        ch_alocada_prof = 0.0
        for item in list_at:
            ch_val = item['ch']
            ch_alocada_prof += ch_val
            comp_lista.append(f"{item['componente']} - {int(ch_val)}H")

        ch_aut = int(getattr(p, 'carga_horaria_autorizada', None) or getattr(p, 'carga_horaria_original', None) or 40)
        ch_aloc = int(ch_alocada_prof)

        total_ch_autorizada += ch_aut
        total_ch_alocada += ch_aloc

        if ch_aloc == ch_aut:
            sit_cad = "COMPLETO"
        elif ch_aloc < ch_aut:
            sit_cad = "INCOMPLETO"
            qtd_incompletos += 1
        else:
            sit_cad = "EXCESSO DE CH"
            qtd_excesso += 1

        dados_consolidados.append({
            'professor': p,
            'ch_total_declarada': ch_aut,
            'ch_alocada': ch_aloc,
            'componentes_lista': comp_lista,
            'situacao_cadastro': sit_cad,
            'observacao': getattr(p, 'observacoes', '') or 'CONFORME INFORMADO PELA ESCOLA'
        })

    return render_template(
        'quadro_informado.html',
        escola=escola_ativa,
        inep_selecionado=e_inep,
        todas_escolas=todas_escolas,
        dados=dados_consolidados,
        n_prof=len(dados_consolidados),
        total_ch_autorizada=total_ch_autorizada,
        total_ch_alocada=total_ch_alocada,
        qtd_incompletos=qtd_incompletos,
        qtd_excesso=qtd_excesso,
        competencia='AGOSTO/2026'
    )