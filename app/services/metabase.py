import os
import requests
import pandas as pd
from flask import current_app
from app.utils.helpers import normalizar_texto

def api_get_turmas_metabase(escola_nome_filtro):
    """
    Autentica no Metabase e consulta o quantitativo de turmas e matrículas da escola.
    """
    url_metabase = current_app.config.get('METABASE_URL') or "https://metabase.see.pb.gov.br"
    card_id = os.getenv("CARD_ID_2026", "123")
    user = os.getenv("MB_USER") or os.getenv("SIAGE_CPF")
    password = os.getenv("MB_PASS") or os.getenv("SIAGE_SENHA")

    if not user or not password:
        return [], 0

    sess = requests.Session()
    try:
        r_login = sess.post(
            f"{url_metabase}/api/session",
            json={"username": user, "password": password},
            timeout=30
        )
        if r_login.status_code != 200:
            return [], 0

        headers = {"X-Metabase-Session": r_login.json()['id']}
        r_data = sess.post(
            f"{url_metabase}/api/card/{card_id}/query/json",
            headers=headers,
            timeout=60
        )
        if r_data.status_code != 200:
            return [], 0

        df = pd.DataFrame(r_data.json())
        if df.empty:
            return [], 0

        df.columns = [c.lower().strip() for c in df.columns]
        col_escola = next((c for c in df.columns if 'escola' in c), None)
        if not col_escola:
            return [], 0

        df = df[df[col_escola].apply(normalizar_texto).str.contains(normalizar_texto(escola_nome_filtro), na=False)]
        if df.empty:
            return [], 0

        col_turma = next((c for c in df.columns if c in ['turma', 'nome_turma', 'descricao']), 'turma')
        col_turno = next((c for c in df.columns if c in ['turno', 'nome_turno']), 'turno')
        col_qtd = next((c for c in df.columns if c in ['vagasocupadas', 'matriculados', 'total', 'qtd']), None)

        def limpar_turno(t):
            t_upper = str(t).upper().strip()
            if 'NOTURNO' in t_upper or 'NOITE' in t_upper:
                return 'NOITE'
            if 'MANH' in t_upper:
                return 'MANHÃ'
            if 'TARDE' in t_upper:
                return 'TARDE'
            if 'INTEGRAL' in t_upper:
                return 'INTEGRAL'
            return t_upper

        turmas = []
        if col_qtd:
            agrupado = df.groupby([col_turma, col_turno])[col_qtd].sum().reset_index()
            for _, row in agrupado.iterrows():
                turmas.append({
                    'nome': str(row[col_turma]),
                    'turno': limpar_turno(row[col_turno]),
                    'qtd': int(row[col_qtd])
                })
        else:
            agrupado = df.groupby([col_turma, col_turno]).size().reset_index(name='qtd')
            for _, row in agrupado.iterrows():
                turmas.append({
                    'nome': str(row[col_turma]),
                    'turno': limpar_turno(row[col_turno]),
                    'qtd': int(row['qtd'])
                })

        return sorted(turmas, key=lambda x: x['nome']), sum(t['qtd'] for t in turmas)
    except Exception as e:
        print(f"❌ Erro na consulta Metabase: {e}")
        return [], 0