# app/services/siage_extractor.py

import os
import json
import requests
from playwright.sync_api import sync_playwright
from app.extensions import db
from app.models.professor import Professor
from app.models.escola import Escola

# IDs Oficiais da 3ª GRE fornecidos nos endpoints do SIAGE
GRE_ID = "222018a3-2be4-4004-9999-7e7c65daa69c"
ANO_LETIVO_ID = "50018994-3fec-4ed7-baec-cc3b869ade81"
URL_BASE_API = "https://api.escola.see.pb.gov.br/api"


def obter_token_siage():
    """Abre o SIAGE via Playwright e captura o Bearer Token de autenticação."""
    print("🌐 [SIAGE API] Iniciando Playwright para obter Token de Acesso...")
    token = None
    sessao_file = "sessao_siage.json"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        if os.path.exists(sessao_file):
            context = browser.new_context(storage_state=sessao_file)
        else:
            context = browser.new_context()

        page = context.new_page()
        page.goto("https://escola.see.pb.gov.br", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Extrai token JWT do LocalStorage
        token = page.evaluate("() => localStorage.getItem('token') || localStorage.getItem('access_token') || localStorage.getItem('jwt')")
        
        # Se não achar no localStorage, lê dos cookies de sessão
        if not token:
            for cookie in context.cookies():
                if 'token' in cookie['name'].lower():
                    token = cookie['value']
                    break

        browser.close()

    if token and not token.startswith("Bearer "):
        token = f"Bearer {token}"

    print("🔑 [SIAGE API] Token capturado com sucesso!")
    return token


def sincronizar_dados_siage_completo():
    """
    Consome os endpoints REST do SIAGE e atualiza as escolas e professores no PostgreSQL.
    """
    token = obter_token_siage()
    if not token:
        print("❌ [SIAGE API] Erro: Não foi possível obter o Token de Autenticação.")
        return False, "Token de autenticação do SIAGE não encontrado."

    headers = {
        "Authorization": token,
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    print("🚀 [SIAGE API] Solicitando lista geral de profissionais da 3ª GRE...")
    
    # Endpoint 1: Lista Geral da 3ª GRE
    url_lista = (
        f"{URL_BASE_API}/Profissional/?"
        f"page=1&numPerPage=2000&limitarQuantidadePagina=false&quantidadeRegistro=2000&"
        f"chegouUltimaPagina=false&anoLetivoId={ANO_LETIVO_ID}&greId={GRE_ID}"
    )

    try:
        res = requests.get(url_lista, headers=headers, timeout=60)
        if res.status_code != 200:
            print(f"❌ [SIAGE API] Erro HTTP {res.status_code}: {res.text}")
            return False, f"Erro HTTP {res.status_code} na API do SIAGE."

        dados = res.json()
        profissionais_lista = dados.get("items") or dados.get("dados") or dados.get("registros") or dados if isinstance(dados, list) else []

        print(f"📊 [SIAGE API] Encontrados {len(profissionais_lista)} registros de profissionais na GRE.")

        total_salvos = 0
        total_atualizados = 0

        for idx, item in enumerate(profissionais_lista, start=1):
            prof_id = item.get("id") or item.get("profissionalId")
            
            if not prof_id:
                continue

            # Dados básicos da lista
            nome = str(item.get("nome") or item.get("servidor") or "").strip()
            matricula = str(item.get("matricula") or "").strip()
            cpf = str(item.get("cpf") or "").strip()
            nome_escola = str(item.get("nomeEscola") or item.get("unidadeEscolar") or "").strip()
            codigo_inep = str(item.get("codigoInep") or item.get("inep") or "").strip().lstrip('0')

            # Endpoint 2: Detalhes específicos do profissional (se disponível)
            url_detalhe = f"{URL_BASE_API}/Profissional/{prof_id}/?page=1&numPerPage=50&limitarQuantidadePagina=false&chegouUltimaPagina=false"
            
            vinculo = str(item.get("vinculo") or item.get("tipoVinc") or "EFETIVO").upper()
            ch_original = float(item.get("cargaHoraria") or item.get("chOriginal") or 40.0)
            ch_autorizada = float(item.get("chAutorizada") or item.get("cargaHorariaAutorizada") or ch_original)
            forma_atuacao = str(item.get("formaAtuacao") or "CUMPRE INTEGRALMENTE A CH NESTA UNIDADE").upper()
            area_plan = str(item.get("areaPlanejamento") or item.get("areaDocencia") or "LINGUAGENS").upper()

            try:
                res_detalhe = requests.get(url_detalhe, headers=headers, timeout=10)
                if res_detalhe.status_code == 200:
                    det = res_detalhe.json()
                    if isinstance(det, dict):
                        cpf = str(det.get("cpf") or cpf).strip()
                        vinculo = str(det.get("vinculo") or det.get("tipoVinc") or vinculo).upper()
                        ch_original = float(det.get("cargaHoraria") or ch_original)
            except Exception:
                pass

            # Localiza a escola no banco PostgreSQL
            escola_obj = None
            if codigo_inep:
                escola_obj = Escola.query.filter(
                    db.func.ltrim(db.func.trim(db.func.cast(Escola.inep_visual, db.String)), '0') == codigo_inep
                ).first()

            if not escola_obj and nome_escola:
                escola_obj = Escola.query.filter(Escola.nome.ilike(f"%{nome_escola}%")).first()

            escola_id = escola_obj.id if escola_obj else None
            escola_inep_db = escola_obj.inep_visual if escola_obj else codigo_inep

            # Upsert do Professor no PostgreSQL
            prof = None
            if cpf:
                prof = Professor.query.filter_by(cpf=cpf).first()
            if not prof and matricula and matricula != "000.000-0":
                prof = Professor.query.filter_by(matricula=matricula).first()
            if not prof and nome:
                prof = Professor.query.filter_by(nome=nome, escola_id=escola_id).first()

            if prof:
                # Atualiza mantendo dados que não estejam vazios
                prof.nome = nome or prof.nome
                prof.matricula = matricula or prof.matricula
                prof.cpf = cpf or prof.cpf
                if escola_id:
                    prof.escola_id = escola_id
                if escola_inep_db:
                    prof.escola_inep = str(escola_inep_db).lstrip('0')
                total_atualizados += 1
            else:
                # Cria novo registro
                novo_prof = Professor(
                    escola_id=escola_id,
                    escola_inep=str(escola_inep_db).lstrip('0') if escola_inep_db else None,
                    matricula=matricula or "000.000-0",
                    cpf=cpf or "",
                    nome=nome or "PROFESSOR SIAGE",
                    vinculo=vinculo,
                    utb_esta_escola="SIM",
                    forma_atuacao=forma_atuacao,
                    carga_horaria_original=ch_original,
                    possui_ch_fora="NÃO",
                    conselho_escolar="NÃO PARTICIPA",
                    areas_planejamento=area_plan,
                    reducao_legal_vigente="NÃO",
                    carga_horaria_autorizada=ch_autorizada,
                    regencia_autorizada=0.0,
                    situacao_cadastro="SIM"
                )
                db.session.add(novo_prof)
                total_salvos += 1

            if idx % 50 == 0:
                db.session.commit()
                print(f"💾 [SIAGE API] Processados {idx}/{len(profissionais_lista)} professores...")

        db.session.commit()
        msg_sucesso = f"✅ Sincronização SIAGE concluída! {total_salvos} novos professores inseridos, {total_atualizados} atualizados."
        print(msg_sucesso)
        return True, msg_sucesso

    except Exception as e:
        db.session.rollback()
        erro_msg = f"❌ [SIAGE API] Falha na extração: {str(e)}"
        print(erro_msg)
        return False, erro_msg