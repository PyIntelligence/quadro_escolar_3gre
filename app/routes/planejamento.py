# app/routes/planejamento.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.extensions import db

planejamento_bp = Blueprint('planejamento', __name__)

DISCIPLINAS_ESCOLA = [
    "LÍNGUA PORTUGUESA",
    "MATEMÁTICA",
    "BIOLOGIA",
    "FÍSICA",
    "QUÍMICA",
    "HISTÓRIA",
    "GEOGRAFIA",
    "LÍNGUA ESTRANGEIRA - INGLÊS",
    "EDUCAÇÃO FÍSICA",
    "ARTE",
    "SOCIOLOGIA",
    "FILOSOFIA",
    "PROJETO DE VIDA",
    "ELETIVAS",
    "ESTUDOS ORIENTADOS"
]


def normalizar_dia(val):
    """Normaliza variações do dia da semana para o padrão do HTML."""
    if not val:
        return ""
    v = str(val).strip().upper()
    mapa = {
        "2": "SEGUNDA-FEIRA", "2ª": "SEGUNDA-FEIRA", "SEG": "SEGUNDA-FEIRA", "SEGUNDA": "SEGUNDA-FEIRA", "SEGUNDA-FEIRA": "SEGUNDA-FEIRA",
        "3": "TERÇA-FEIRA", "3ª": "TERÇA-FEIRA", "TER": "TERÇA-FEIRA", "TERCA": "TERÇA-FEIRA", "TERÇA": "TERÇA-FEIRA", "TERÇA-FEIRA": "TERÇA-FEIRA",
        "4": "QUARTA-FEIRA", "4ª": "QUARTA-FEIRA", "QUA": "QUARTA-FEIRA", "QUARTA": "QUARTA-FEIRA", "QUARTA-FEIRA": "QUARTA-FEIRA",
        "5": "QUINTA-FEIRA", "5ª": "QUINTA-FEIRA", "QUI": "QUINTA-FEIRA", "QUINTA": "QUINTA-FEIRA", "QUINTA-FEIRA": "QUINTA-FEIRA",
        "6": "SEXTA-FEIRA", "6ª": "SEXTA-FEIRA", "SEX": "SEXTA-FEIRA", "SEXTA": "SEXTA-FEIRA", "SEXTA-FEIRA": "SEXTA-FEIRA",
        "7": "SÁBADO", "SAB": "SÁBADO", "SABADO": "SÁBADO", "SÁBADO": "SÁBADO"
    }
    return mapa.get(v, v)


def normalizar_hora(val):
    """Normaliza horários (ex: '07:00:00' -> '07:00')."""
    if not val:
        return ""
    v = str(val).strip()
    if len(v) >= 5 and ":" in v:
        return v[:5]
    return v


class EscolaView:
    def __init__(self, e_id, inep, nome):
        self.id = e_id
        self.inep_visual = str(inep or '').strip()
        self.codigo_inep = str(inep or '').strip()
        self.inep = str(inep or '').strip()
        self.nome = nome or "ESCOLA"
        self.unidade_escolar = nome or "ESCOLA"


def resolver_escola_oficial(val):
    if not val:
        return None
    val_str = str(val).strip()
    val_clean = val_str.lstrip('0')

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

    try:
        sql3 = db.text("""
            SELECT id, codigo_inep AS inep_visual, unidade_escolar AS nome 
            FROM escola_gestao 
            WHERE LTRIM(TRIM(CAST(codigo_inep AS VARCHAR)), '0') = :clean
               OR TRIM(CAST(codigo_inep AS VARCHAR)) = :raw
            LIMIT 1
        """)
        row = db.session.execute(sql3, {"clean": val_clean, "raw": val_str}).fetchone()
        if row:
            return row
    except Exception:
        db.session.rollback()

    return None


def obter_escola_atual():
    candidatos = [
        request.args.get('inep'),
        request.args.get('codigo_inep'),
        session.get('active_inep'),
        session.get('escola_inep'),
    ]
    for cand in candidatos:
        row = resolver_escola_oficial(cand)
        if row:
            session['active_inep'] = str(row[1] or '').strip()
            return EscolaView(row[0], str(row[1] or '').strip(), str(row[2] or '').strip())

    try:
        row = db.session.execute(db.text("SELECT id, inep_visual, nome FROM escola ORDER BY id LIMIT 1")).fetchone()
        if row:
            return EscolaView(row[0], str(row[1] or '').strip(), str(row[2] or '').strip())
    except Exception:
        db.session.rollback()

    return None


@planejamento_bp.route('/planejamento', methods=['GET', 'POST'])
def planejamento():
    escola_obj = obter_escola_atual()
    if not escola_obj:
        flash('Selecione uma escola válida para acessar o Planejamento.', 'warning')
        return redirect('/escolas')

    inep_param = request.args.get('inep') or escola_obj.codigo_inep
    inep_clean = str(inep_param or '').strip().lstrip('0')
    e_id = escola_obj.id

    # 1. Estruturação da Tabela
    try:
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS planejamento (
                id SERIAL PRIMARY KEY,
                escola_id INT,
                codigo_inep VARCHAR(20),
                ano_letivo VARCHAR(10),
                area_conhecimento VARCHAR(150),
                turma_nome VARCHAR(100),
                dia_semana VARCHAR(50),
                horario_inicio VARCHAR(20),
                horario_fim VARCHAR(20),
                turno VARCHAR(50),
                responsavel VARCHAR(150),
                observacao TEXT
            );
            ALTER TABLE planejamento ADD COLUMN IF NOT EXISTS ano_letivo VARCHAR(10);
            ALTER TABLE planejamento DROP CONSTRAINT IF EXISTS planejamento_escola_id_fkey;
            ALTER TABLE planejamento ALTER COLUMN escola_id DROP NOT NULL;
            ALTER TABLE planejamento ALTER COLUMN codigo_inep DROP NOT NULL;
            ALTER TABLE planejamento ALTER COLUMN area_conhecimento DROP NOT NULL;
        """))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ESTRUTURA BANCO PLANEJAMENTO]: {e}")

    # 2. Ações do Formulário (POST)
    if request.method == 'POST':
        action = request.form.get('action', 'save')
        if action == 'delete':
            reg_id = request.form.get('id')
            if reg_id:
                try:
                    db.session.execute(db.text("DELETE FROM planejamento WHERE id = :id"), {"id": reg_id})
                    db.session.commit()
                    flash('Linha de planejamento removida!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Erro ao remover: {str(e)}', 'danger')

        elif action in ['add', 'save', 'update']:
            reg_id = request.form.get('id')
            area = request.form.get('area_conhecimento', '').strip().upper()
            turma = request.form.get('turma_nome', '').strip().upper()
            dia = normalizar_dia(request.form.get('dia_semana', ''))
            h_ini = normalizar_hora(request.form.get('horario_inicio', ''))
            h_fim = normalizar_hora(request.form.get('horario_fim', ''))
            turno = request.form.get('turno', '').strip().upper()
            resp = request.form.get('responsavel', '').strip().upper()
            obs = request.form.get('observacao', '').strip().upper()

            if area:
                try:
                    if reg_id and str(reg_id).isdigit() and int(reg_id) > 0:
                        sql_upd = db.text("""
                            UPDATE planejamento 
                            SET area_conhecimento = :area, turma_nome = :turma, dia_semana = :dia,
                                horario_inicio = :h_ini, horario_fim = :h_fim, turno = :turno,
                                responsavel = :resp, observacao = :obs
                            WHERE id = :id
                        """)
                        db.session.execute(sql_upd, {
                            "id": int(reg_id), "area": area, "turma": turma, "dia": dia,
                            "h_ini": h_ini, "h_fim": h_fim, "turno": turno, "resp": resp, "obs": obs
                        })
                    else:
                        sql_ins = db.text("""
                            INSERT INTO planejamento (
                                escola_id, codigo_inep, ano_letivo, area_conhecimento, turma_nome, dia_semana,
                                horario_inicio, horario_fim, turno, responsavel, observacao
                            ) VALUES (:e_id, :inep, '2026', :area, :turma, :dia, :h_ini, :h_fim, :turno, :resp, :obs)
                        """)
                        db.session.execute(sql_ins, {
                            "e_id": e_id, "inep": inep_clean, "area": area, "turma": turma,
                            "dia": dia, "h_ini": h_ini, "h_fim": h_fim, "turno": turno, "resp": resp, "obs": obs
                        })
                    db.session.commit()
                    flash('Planejamento salvo!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Erro ao salvar: {str(e)}', 'danger')

        return redirect(url_for('planejamento.planejamento', inep=inep_param))

    # 3. Povoamento das Disciplinas Padrão
    try:
        db.session.execute(db.text("""
            DELETE FROM planejamento 
            WHERE (
                UPPER(TRIM(area_conhecimento)) IN ('COMPONENTE CURRICULAR', 'COMPONENTE', '')
                OR area_conhecimento IS NULL
            ) AND (
                escola_id = :e_id 
                OR LTRIM(TRIM(CAST(COALESCE(codigo_inep, '') AS VARCHAR)), '0') = :clean
            )
        """), {"e_id": e_id, "clean": inep_clean})
        db.session.commit()

        sql_profs = db.text("""
            SELECT * FROM professores 
            WHERE escola_id = :e_id
               OR LTRIM(TRIM(CAST(COALESCE(codigo_inep, '') AS VARCHAR)), '0') = :clean
               OR TRIM(CAST(COALESCE(codigo_inep, '') AS VARCHAR)) = :raw
        """)
        profs_encontrados = db.session.execute(sql_profs, {
            "e_id": e_id,
            "clean": inep_clean,
            "raw": str(inep_param).strip()
        }).mappings().fetchall()

        disciplinas_extraidas = []
        for p in profs_encontrados:
            disc = str(p.get('disciplina') or p.get('componente') or p.get('materia') or '').strip().upper()
            if disc and disc not in ['COMPONENTE CURRICULAR', 'COMPONENTE', 'PROFESSOR', 'S/M', 'NONE']:
                if disc not in disciplinas_extraidas:
                    disciplinas_extraidas.append(disc)

        disciplinas_alvo = disciplinas_extraidas if disciplinas_extraidas else DISCIPLINAS_ESCOLA

        for disc in disciplinas_alvo:
            sql_check = db.text("""
                SELECT COUNT(*) FROM planejamento 
                WHERE UPPER(TRIM(area_conhecimento)) = :disc
                  AND (escola_id = :e_id OR LTRIM(TRIM(CAST(COALESCE(codigo_inep, '') AS VARCHAR)), '0') = :clean)
            """)
            qtd = db.session.execute(sql_check, {"disc": disc, "e_id": e_id, "clean": inep_clean}).scalar() or 0

            if qtd == 0:
                sql_p_ins = db.text("""
                    INSERT INTO planejamento (escola_id, codigo_inep, ano_letivo, area_conhecimento, turno)
                    VALUES (:e_id, :inep, '2026', :disc, 'INTEGRAL')
                """)
                db.session.execute(sql_p_ins, {
                    "e_id": e_id,
                    "inep": inep_clean,
                    "disc": disc
                })
                print(f"[POPULOU PLANEJAMENTO] Disciplina inserida: {disc}")

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO NA SINCRONIZAÇÃO DE DISCIPLINAS]: {e}")

    # 4. Normalização na Busca
    planejamentos = []
    try:
        sql_sel = db.text("""
            SELECT * FROM planejamento 
            WHERE escola_id = :e_id OR LTRIM(TRIM(CAST(COALESCE(codigo_inep, '') AS VARCHAR)), '0') = :clean
            ORDER BY id ASC
        """)
        rows = db.session.execute(sql_sel, {"e_id": e_id, "clean": inep_clean}).mappings().fetchall()
        
        for r in rows:
            item = dict(r)
            item['dia_semana'] = normalizar_dia(item.get('dia_semana'))
            item['horario_inicio'] = normalizar_hora(item.get('horario_inicio'))
            item['horario_fim'] = normalizar_hora(item.get('horario_fim'))
            planejamentos.append(item)

    except Exception as e:
        db.session.rollback()
        print(f"[ERRO BUSCA PLANEJAMENTO]: {e}")

    return render_template(
        'planejamento.html',
        escola=escola_obj,
        registro=escola_obj,
        inep=inep_param,
        inep_selecionado=inep_param,
        planejamentos=planejamentos,
        registros=planejamentos
    )


@planejamento_bp.route('/autosave_planejamento', methods=['POST'])
def autosave_planejamento():
    data = request.get_json(silent=True) or {}
    reg_id = data.get('id')
    campo = data.get('campo')
    valor_raw = str(data.get('valor', '')).strip().upper()

    campos_validos = {
        'area_conhecimento', 'turma_nome', 'dia_semana', 'horario_inicio',
        'horario_fim', 'turno', 'responsavel', 'observacao'
    }

    if not reg_id or campo not in campos_validos:
        return jsonify({"status": "erro", "mensagem": "Dados inválidos"}), 400

    valor = valor_raw
    if campo == 'dia_semana':
        valor = normalizar_dia(valor_raw)
    elif campo in ['horario_inicio', 'horario_fim']:
        valor = normalizar_hora(valor_raw)

    try:
        sql_upd = db.text(f"UPDATE planejamento SET {campo} = :val WHERE id = :id")
        db.session.execute(sql_upd, {"val": valor, "id": reg_id})
        db.session.commit()
        return jsonify({"status": "sucesso"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "erro", "mensagem": str(e)}), 500