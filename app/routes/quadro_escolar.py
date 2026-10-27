# app/routes/quadro_escolar.py

from flask import Blueprint, render_template, request, session, redirect, url_for
from app.extensions import db

quadro_escolar_bp = Blueprint('quadro_escolar', __name__)


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


@quadro_escolar_bp.route('/quadro_escolar', methods=['GET', 'POST'])
def quadro_escolar():
    # 1. Identifica a escola na URL ou na Sessão
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
            print(f"[ERRO QUADRO ESCOLAR - BUSCA ESCOLA]: {e}")
            db.session.rollback()

    if not escola_row:
        try:
            sql_f = db.text("SELECT id, inep_visual, nome FROM escola ORDER BY id LIMIT 1")
            escola_row = db.session.execute(sql_f).fetchone()
        except Exception as e:
            print(f"[ERRO QUADRO ESCOLAR - ESCOLA FALLBACK]: {e}")
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

    # Trata salvamento de Manifestação / Justificativa
    if request.method == 'POST':
        action = request.form.get('action')
        componente = request.form.get('componente')
        manifestacao = request.form.get('manifestacao', '')
        justificativa = request.form.get('justificativa', '')

        if action == 'salvar_manifestacao' and e_id and componente:
            try:
                sql_save = db.text("""
                    INSERT INTO manifestacao_escola (escola_id, componente, manifestacao, justificativa)
                    VALUES (:eid, :comp, :manif, :just)
                    ON CONFLICT (escola_id, componente) 
                    DO UPDATE SET manifestacao = EXCLUDED.manifestacao, justificativa = EXCLUDED.justificativa
                """)
                db.session.execute(sql_save, {
                    "eid": e_id, 
                    "comp": componente, 
                    "manif": manifestacao, 
                    "just": justificativa
                })
                db.session.commit()
            except Exception as e:
                print(f"[AVISO QUADRO ESCOLAR - SALVAR MANIFESTAÇÃO]: {e}")
                db.session.rollback()

        return redirect(url_for('quadro_escolar.quadro_escolar', inep=e_inep))

    # 2. Carrega lista de todas as escolas para o Dropdown
    todas_escolas = []
    try:
        sql_todas = db.text("""
            SELECT id, 
                   COALESCE(inep_visual, CAST(id AS VARCHAR)) as inep_visual, 
                   nome 
            FROM escola 
            ORDER BY nome
        """)
        rows_todas = db.session.execute(sql_todas).fetchall()
        todas_escolas = [EscolaView(r[0], r[1], r[2]) for r in rows_todas]
    except Exception as e:
        print(f"[ERRO QUADRO ESCOLAR - TODAS ESCOLAS]: {e}")
        db.session.rollback()

    # 3. Componentes Curriculares da Matriz
    componentes_base = [
        {"nome": "APROFUNDAMENTO", "turmas": 6, "demanda": 12},
        {"nome": "ARTE", "turmas": 30, "demanda": 33},
        {"nome": "BASE TÉCNICA", "turmas": 21, "demanda": 270},
        {"nome": "BIOLOGIA", "turmas": 30, "demanda": 63},
        {"nome": "EDUCAÇÃO DIGITAL", "turmas": 21, "demanda": 21},
        {"nome": "EDUCAÇÃO FÍSICA", "turmas": 30, "demanda": 51},
        {"nome": "FILOSOFIA", "turmas": 30, "demanda": 45},
        {"nome": "FÍSICA", "turmas": 30, "demanda": 63},
        {"nome": "GEOGRAFIA", "turmas": 30, "demanda": 63},
        {"nome": "HISTÓRIA", "turmas": 30, "demanda": 63},
        {"nome": "LÍNGUA ESPANHOLA", "turmas": 30, "demanda": 30},
        {"nome": "LÍNGUA INGLESA", "turmas": 30, "demanda": 45},
        {"nome": "LÍNGUA PORTUGUESA", "turmas": 30, "demanda": 96},
        {"nome": "MATEMÁTICA", "turmas": 30, "demanda": 96},
        {"nome": "QUÍMICA", "turmas": 30, "demanda": 63},
        {"nome": "SOCIOLOGIA", "turmas": 30, "demanda": 45}
    ]

    names_set = {c["nome"].upper() for c in componentes_base}

    # Carrega as atuações do banco
    ch_alocada_por_comp = {}
    outras_atuacoes_raw = []

    if e_id or e_inep:
        clean_inep = e_inep.lstrip('0')
        try:
            sql_at = db.text("""
                SELECT atividade_componente, professor_nome, ch_semanal
                FROM atuacao
                WHERE escola_id = :eid 
                   OR escola_id IN (
                       SELECT id FROM escola 
                       WHERE LTRIM(TRIM(CAST(inep_visual AS VARCHAR)), '0') = :inep
                   )
            """)
            rows_at = db.session.execute(sql_at, {"eid": e_id, "inep": clean_inep}).fetchall()
            for r in rows_at:
                comp_raw = str(r[0] or '').strip().upper()
                prof_nome = str(r[1] or '').strip().upper()
                ch_val = float(r[2] or 0.0)

                if comp_raw in names_set:
                    ch_alocada_por_comp[comp_raw] = ch_alocada_por_comp.get(comp_raw, 0.0) + ch_val
                elif comp_raw:
                    outras_atuacoes_raw.append({
                        "atividade_componente": comp_raw,
                        "profissionais": prof_nome,
                        "ch_semanal": ch_val
                    })
        except Exception as e:
            print(f"[AVISO QUADRO ESCOLAR - BUSCA ATUAÇÕES]: {e}")
            db.session.rollback()

    # Carrega manifestações salvas previamente
    manifestacoes_salvas = {}
    if e_id:
        try:
            sql_m = db.text("SELECT componente, manifestacao, justificativa FROM manifestacao_escola WHERE escola_id = :eid")
            rows_m = db.session.execute(sql_m, {"eid": e_id}).fetchall()
            for row in rows_m:
                manifestacoes_salvas[str(row[0]).upper()] = {
                    "manifestacao": row[1] or "",
                    "justificativa": row[2] or ""
                }
        except Exception:
            db.session.rollback()

    # Monta Tabela 1: Matriz Curricular
    tabela_matriz = []
    for idx, c in enumerate(componentes_base, start=1):
        nome_comp = c["nome"]
        demanda = c["demanda"]
        ch_inf = int(ch_alocada_por_comp.get(nome_comp, demanda))

        if ch_inf == demanda:
            diag_auto = "COBERTURA INFORMADA COMPATÍVEL"
            diag_final = "INFORMATIVO - NÃO IMPEDITIVO"
        elif ch_inf < demanda:
            diag_auto = "POSSÍVEL VACÂNCIA"
            diag_final = "SITUAÇÃO PENDENTE DE MANIFESTAÇÃO"
        else:
            diag_auto = "EXCESSO DE CH"
            diag_final = "INFORMATIVO - NÃO IMPEDITIVO"

        m_dados = manifestacoes_salvas.get(nome_comp, {})

        tabela_matriz.append({
            "num": idx,
            "componente": nome_comp,
            "turmas": c["turmas"],
            "demanda_matriz": demanda,
            "ch_informada": ch_inf,
            "diag_auto": diag_auto,
            "manifestacao": m_dados.get("manifestacao", ""),
            "justificativa": m_dados.get("justificativa", ""),
            "diag_final": diag_final
        })

    print(f"\n[DIAGNÓSTICO QUADRO ESCOLAR] Escola: {e_nome} | INEP: {e_inep} | Linhas da Matriz: {len(tabela_matriz)} | Outras Atuações: {len(outras_atuacoes_raw)}\n")

    # Monta Tabela 2: Outras Atuações
    tabela_outras = []
    for idx, item in enumerate(outras_atuacoes_raw, start=1):
        tabela_outras.append({
            "num": idx,
            "atividade_componente": item["atividade_componente"],
            "profissionais": item["profissionais"] or "COMPLEMENTAR",
            "ch_informada": int(item["ch_semanal"]),
            "grupo_atuacao": "COMPLEMENTAR / APOIO",
            "natureza_ch": "REGÊNCIA / PROJETO",
            "impacta_matriz": "NÃO",
            "classificacao": "ATIVIDADE ESCOLAR",
            "situacao": "REGISTRO VÁLIDO"
        })

    return render_template(
        'quadro_escolar.html',
        escola=escola_ativa,
        inep_selecionado=e_inep,
        todas_escolas=todas_escolas,
        tabela_matriz=tabela_matriz,
        tabela_outras=tabela_outras,
        competencia='AGOSTO/2026'
    )