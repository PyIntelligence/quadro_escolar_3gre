import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.extensions import db
from app.models.escola import EscolaGestao
from app.models.professor import Professor
from app.utils.helpers import normalizar_texto, encontrar_lista_oculta

FAKE_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
URL_SIAGE_BASE = "https://escola.see.pb.gov.br"
ID_GRE_3 = "3"

def auto_login_selenium_robusto():
    cpf = os.getenv("SIAGE_CPF")
    senha = os.getenv("SIAGE_SENHA")
    if not cpf or not senha:
        print("⚠️ CPF ou Senha do SIAGE não configurados no .env")
        return None

    print(f"🔄 [ROBÔ] Iniciando Login Automático ({cpf})...")

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")

    driver = None
    token = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.get(URL_SIAGE_BASE)
        wait = WebDriverWait(driver, 25)
        time.sleep(3)

        try:
            wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/app-root/app-layout-no-auth/app-login/div/div/div[1]/form/div[3]/div/div/div/input'))).send_keys(cpf)
        except Exception:
            driver.find_element(By.XPATH, '//input[@formcontrolname="cpf"]').send_keys(cpf)

        try:
            wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/app-root/app-layout-no-auth/app-login/div/div/div[1]/form/div[4]/div/div[1]/div/input'))).send_keys(senha)
        except Exception:
            driver.find_element(By.XPATH, '//input[@type="password"]').send_keys(senha)

        time.sleep(1)
        try:
            driver.find_element(By.XPATH, '/html/body/app-root/app-layout-no-auth/app-login/div/div/div[1]/form/div[5]/div/button').click()
        except Exception:
            driver.execute_script("document.querySelector('button[type=submit]').click()")

        time.sleep(4)
        print("⏳ [ROBÔ] Aguardando Token...")
        start_time = time.time()
        while time.time() - start_time < 30:
            token = driver.execute_script("return window.localStorage.getItem('seectpb.token');")
            if token and len(token) > 20:
                print("✅ [ROBÔ] Token capturado!")
                break
            time.sleep(1)
    except Exception as e:
        print(f"❌ Erro Selenium: {e}")
    finally:
        if driver:
            driver.quit()

    return token.replace('"', '').replace("'", "") if token else None

def api_fetch(url, token, params=None):
    if not token:
        return {}
    headers = {'Authorization': f'Bearer {token}', 'User-Agent': FAKE_USER_AGENT}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}

def api_get_corpo_diretivo_completo(escola_id_interno, token, ano_id=2026):
    url = f"{URL_SIAGE_BASE}/api/QuadroFuncional/escola/alocacao/corpo-diretivo-alocados-v2"
    params = {'anoLetivoId': ano_id, 'escolaId': escola_id_interno, 'page': 1, 'numPerpage': 100, 'tipoOrdenacao': 'DESC'}
    data = api_fetch(url, token, params)
    lista = encontrar_lista_oculta(data)
    equipe = []
    if lista:
        for p in lista:
            nome = p.get('nomeServidor') or p.get('nome')
            if not nome:
                continue
            equipe.append({
                'nome': nome,
                'matricula': p.get('matricula'),
                'cargo': str(p.get('descricaoFuncao') or p.get('funcao') or ''),
                'telefone': p.get('telefone') or ''
            })
    equipe.sort(key=lambda x: 1 if 'DIRETOR' in normalizar_texto(x['cargo']) else 99)
    return equipe

def sincronizar_escolas_gre3(token):
    print("📥 [AUTOMAÇÃO] Sincronizando escolas da 3ª GRE...")
    url = f"{URL_SIAGE_BASE}/api/escola"
    params = {'greId': ID_GRE_3, 'gerenciaRegionalId': ID_GRE_3, 'somenteAtivas': 'true', 'numPerPage': 1000}

    data = api_fetch(url, token, params)
    lista = encontrar_lista_oculta(data)
    if not lista:
        return 0

    novas_escolas = 0
    for x in lista:
        enome = x.get('nome') or x.get('escola')
        inep_vis = str(x.get('codigoInep') or x.get('inep') or '')

        if inep_vis and enome:
            existente = EscolaGestao.query.filter_by(codigo_inep=inep_vis).first()
            if not existente:
                nova = EscolaGestao(
                    codigo_inep=inep_vis,
                    unidade_escolar=enome,
                    gre="3ª GRE",
                    municipio=x.get('municipio', 'MUNICÍPIO MODELO'),
                    endereco=x.get('endereco'),
                    email=x.get('email'),
                    telefone=x.get('telefone'),
                    zona=x.get('zona')
                )
                db.session.add(nova)
                novas_escolas += 1

    try:
        db.session.commit()
        print(f"✅ [AUTOMAÇÃO] {novas_escolas} novas escolas salvas!")
    except Exception as e:
        db.session.rollback()
        print(f"❌ [AUTOMAÇÃO] Erro ao salvar escolas: {e}")

    return novas_escolas