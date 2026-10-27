# app/services/siage_smart_sync.py

import os
import sys
import time
import json
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from app.extensions import db

load_dotenv()

SIAGE_URL = os.getenv('SIAGE_URL', 'https://escola.see.pb.gov.br')
SIAGE_USUARIO = os.getenv('SIAGE_USUARIO') or os.getenv('SIAGE_CPF')
SIAGE_SENHA = os.getenv('SIAGE_SENHA') or os.getenv('SIAGE_PASSWORD')

NOME_ARQUIVO_SESSAO = "sessao_siage.json"

GRE_ID_3 = "222018a3-2be4-4004-9999-7e7c65daa69c"  # 3ª GRE
ANO_LETIVO_ID = "50018994-3fec-4ed7-baec-cc3b869ade81"  # ID do SIAGE para 2026
ANO_LETIVO_NUMERO = "2026"  # Ano de referência
API_HOST = "https://api.escola.see.pb.gov.br/api"

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
    try:
        from app.models.planejamento import PlanejamentoArea as Planejamento
    except ImportError:
        Planejamento = None


# ==============================================================================
# FUNÇÕES AUXILIARES DE TRATAMENTO E FORMATACAO
# ==============================================================================

def formatar_cpf(val):
    if not val:
        return None
    digits = ''.join(c for c in str(val) if c.isdigit())
    if len(digits) == 11 and set(digits) != {'0'}:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return None


def cpf_eh_invalido_ou_vazio(val):
    if not val:
        return True
    val_str = str(val).strip()
    if val_str in ['', 'None', '0', '000.000.000-00', '00000000000', '-']:
        return True
    digits = ''.join(c for c in val_str if c.isdigit())
    if len(digits) != 11 or set(digits) == {'0'}:
        return True
    return False


def valor_eh_vazio(val):
    if val is None:
        return True
    val_str = str(val).strip().upper()
    return val_str in ['', 'NONE', 'NULL', '0', '-']


def normalizar_dia_semana(val):
    if not val:
        return ""
    v = str(val).strip().upper()
    mapa_dias = {
        "2": "SEGUNDA-FEIRA", "2ª": "SEGUNDA-FEIRA", "SEG": "SEGUNDA-FEIRA", "SEGUNDA": "SEGUNDA-FEIRA", "SEGUNDA-FEIRA": "SEGUNDA-FEIRA",
        "3": "TERÇA-FEIRA", "3ª": "TERÇA-FEIRA", "TER": "TERÇA-FEIRA", "TERCA": "TERÇA-FEIRA", "TERÇA": "TERÇA-FEIRA", "TERÇA-FEIRA": "TERÇA-FEIRA",
        "4": "QUARTA-FEIRA", "4ª": "QUARTA-FEIRA", "QUA": "QUARTA-FEIRA", "QUARTA": "QUARTA-FEIRA", "QUARTA-FEIRA": "QUARTA-FEIRA",
        "5": "QUINTA-FEIRA", "5ª": "QUINTA-FEIRA", "QUI": "QUINTA-FEIRA", "QUINTA": "QUINTA-FEIRA", "QUINTA-FEIRA": "QUINTA-FEIRA",
        "6": "SEXTA-FEIRA", "6ª": "SEXTA-FEIRA", "SEX": "SEXTA-FEIRA", "SEXTA": "SEXTA-FEIRA", "SEXTA-FEIRA": "SEXTA-FEIRA",
        "7": "SÁBADO", "SAB": "SÁBADO", "SABADO": "SÁBADO", "SÁBADO": "SÁBADO"
    }
    return mapa_dias.get(v, v)


def normalizar_horario(val):
    if not val:
        return ""
    v = str(val).strip()
    if len(v) >= 5 and ":" in v:
        return v[:5]
    return v


def extrair_lista_generica(dados):
    if isinstance(dados, list):
        return dados
    if not isinstance(dados, dict):
        return []

    if "data" in dados and isinstance(dados["data"], dict):
        inner_data = dados["data"]
        if "page" in inner_data and isinstance(inner_data["page"], dict):
            if "data" in inner_data["page"] and isinstance(inner_data["page"]["data"], list):
                return inner_data["page"]["data"]
        if "data" in inner_data and isinstance(inner_data["data"], list):
            return inner_data["data"]

    if "page" in dados and isinstance(dados["page"], dict):
        if "data" in dados["page"] and isinstance(dados["page"]["data"], list):
            return dados["page"]["data"]

    for chave in ['items', 'content', 'dados', 'resultado', 'data', 'value', 'values', 'escolas', 'profissionais', 'turmas']:
        if chave in dados and isinstance(dados[chave], list):
            return dados[chave]

    for key, val in dados.items():
        if isinstance(val, list):
            return val
        elif isinstance(val, dict):
            res = extrair_lista_generica(val)
            if res:
                return res

    return []


class RobosiageInteligente:
    def __init__(self, callback_progresso=None):
        self.usuario = SIAGE_USUARIO
        self.senha = SIAGE_SENHA
        self.token = None
        self.callback_progresso = callback_progresso

    def _notificar(self, pct, msg):
        print(f"[ROBÔ SIAGE] [{pct}%] {msg}", flush=True)
        if self.callback_progresso:
            self.callback_progresso(pct, msg)

    def sincronizar_tudo_incremental(self):
        self._notificar(2, "⚙️ Verificando credenciais do SIAGE no .env...")

        if not self.usuario or not self.senha:
            msg_erro = "⚠️ SIAGE_CPF/SIAGE_USUARIO ou SIAGE_SENHA não foram configurados no .env!"
            self._notificar(0, msg_erro)
            return False, msg_erro

        self._notificar(5, "🌐 Iniciando navegador Playwright (Chromium em segundo plano)...")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            if os.path.exists(NOME_ARQUIVO_SESSAO):
                context = browser.new_context(storage_state=NOME_ARQUIVO_SESSAO)
            else:
                context = browser.new_context()

            page = context.new_page()

            def capturar_token(request):
                url = request.url
                if "api.escola.see.pb.gov.br" in url:
                    headers = request.headers
                    auth_header = headers.get("authorization") or headers.get("Authorization")
                    if auth_header and "Bearer" in auth_header:
                        self.token = auth_header

            page.on("request", capturar_token)

            try:
                self._notificar(10, "🔗 Acessando o portal SIAGE (https://escola.see.pb.gov.br)...")
                page.goto(SIAGE_URL, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                # Preenchimento automático de login
                for sel in ["input[name*='cpf']", "input[name*='usuario']", "input[type='text']", "#cpf"]:
                    try:
                        loc = page.locator(sel).first
                        if loc.is_visible(timeout=1000):
                            loc.fill(self.usuario)
                            break
                    except Exception:
                        pass

                for sel in ["input[type='password']", "#senha"]:
                    try:
                        loc = page.locator(sel).first
                        if loc.is_visible(timeout=1000):
                            loc.fill(self.senha)
                            break
                    except Exception:
                        pass

                self._notificar(15, "⚡ Efetuando login e capturando Token de Acesso...")
                for sel in ["button[type='submit']", "button:has-text('Entrar')", "button:has-text('Acessar')"]:
                    try:
                        loc = page.locator(sel).first
                        if loc.is_visible(timeout=1000):
                            loc.click()
                            break
                    except Exception:
                        pass

                page.wait_for_timeout(4000)

                if not self.token:
                    script_js = """
                    () => {
                        for (let i = 0; i < localStorage.length; i++) {
                            let key = localStorage.key(i);
                            let val = localStorage.getItem(key);
                            if (val && val.includes("eyJ")) {
                                if (val.startsWith("eyJ")) return "Bearer " + val;
                            }
                        }
                        return null;
                    }
                    """
                    self.token = page.evaluate(script_js)

                if not self.token:
                    return False, "Token Bearer não encontrado após tentativa de login."

                try:
                    context.storage_state(path=NOME_ARQUIVO_SESSAO)
                except Exception:
                    pass

                # 1. Escolas da GRE
                self._notificar(25, "📚 Solicitando lista de escolas da 3ª GRE...")
                escolas_api = self._obter_escolas_da_gre(page)
                if not escolas_api:
                    return False, "Nenhuma escola foi retornada pela API do SIAGE."

                # 2. Quadros / Planejamentos por Área
                self._notificar(40, "📅 Extraindo planejamentos e quadros das escolas...")
                planejamentos = self._extrair_planejamentos_da_gre(page, escolas_api)

                # 3. Professores e CPFs
                self._notificar(60, "👥 Extraindo lista de professores por escola...")
                profissionais = self._extrair_profissionais_por_escolas(page, escolas_api)

                self._notificar(75, "🚀 Recuperando CPFs pendentes em lote...")
                self._recuperar_cpfs_em_lotes(page, profissionais)

                browser.close()

                # 4. Sincronização no PostgreSQL
                self._notificar(85, "🏫 Sincronizando cadastro de escolas no PostgreSQL...")
                mapa_escolas = self._sincronizar_escolas_no_postgres(escolas_api)

                self._notificar(90, "💾 Gravando grade de planejamentos no PostgreSQL...")
                self._salvar_planejamento_turmas_no_postgres(mapa_escolas, planejamentos)

                self._notificar(95, "🔄 Atualizando professores no PostgreSQL...")
                tot_profs = self._salvar_professores_no_postgres(profissionais, mapa_escolas)

                self._notificar(98, "⚡ Consolidando tabela de atuação dos professores...")
                self._sincronizar_atuacao_professores_no_postgres(mapa_escolas, planejamentos, profissionais)

                self._notificar(100, "🎉 Sincronização concluída com sucesso!")
                return True, f"Processamento concluído. {len(escolas_api)} escolas e {tot_profs} professores sincronizados."

            except Exception as e:
                db.session.rollback()
                msg_err = f"Erro na execução do Playwright: {str(e)}"
                self._notificar(0, f"❌ {msg_err}")
                return False, msg_err
            finally:
                try:
                    browser.close()
                except Exception:
                    pass

    # =========================================================================
    # RASPAGEM E EXTRAÇÃO COM PLAYWRIGHT
    # =========================================================================

    def _obter_escolas_da_gre(self, page):
        url_escolas = f"{API_HOST}/autocomplete/escola-by-gre?greId={GRE_ID_3}"
        script_js = """
        async ({ url, token }) => {
            let headers = { "Content-Type": "application/json" };
            if (token) headers["Authorization"] = token;
            try {
                const resp = await fetch(url, { headers: headers });
                const json = await resp.json();
                return { status: resp.status, data: json };
            } catch (e) {
                return { status: 500, error: e.toString() };
            }
        }
        """
        res = page.evaluate(script_js, {"url": url_escolas, "token": self.token})
        dados = res.get("data")
        return extrair_lista_generica(dados)

    def _extrair_detalhes_quadro_planejamento(self, page, quadro_id, formacao_turma_id):
        url_dados_turma = f"{API_HOST}/CurriculoQuadroHorario/dados-turma?formacaoTurmaId={formacao_turma_id}&quadroId={quadro_id}&isVisualizar=true"
        url_componentes = f"{API_HOST}/CurriculoQuadroHorario/dados-componentes-turma?quadroId={quadro_id}"

        script_js = """
        async ({ url, token }) => {
            let headers = { "Content-Type": "application/json" };
            if (token) headers["Authorization"] = token;
            try {
                const resp = await fetch(url, { headers: headers });
                if (resp.status === 200) return await resp.json();
            } catch(e) {}
            return null;
        }
        """
        res_turma = page.evaluate(script_js, {"url": url_dados_turma, "token": self.token})
        res_comp = page.evaluate(script_js, {"url": url_componentes, "token": self.token})

        return {
            "turma": res_turma.get("data") if isinstance(res_turma, dict) else None,
            "componentes": res_comp.get("data") if isinstance(res_comp, dict) else []
        }

    def _extrair_planejamentos_da_gre(self, page, escolas_api):
        script_js = """
        async ({ url, token }) => {
            let headers = { "Content-Type": "application/json" };
            if (token) headers["Authorization"] = token;
            try {
                const resp = await fetch(url, { headers: headers });
                if (resp.status === 200) return await resp.json();
            } catch(e) {}
            return null;
        }
        """
        todos_planejamentos = []
        for esc in escolas_api:
            if not isinstance(esc, dict):
                continue
            escola_id_siage = str(esc.get('id') or esc.get('escolaId') or esc.get('value') or '').strip()
            inep = str(esc.get('codigoInep') or esc.get('inep') or '').strip()
            if not escola_id_siage:
                continue

            url_turmas = f"{API_HOST}/CurriculoQuadroHorario/turmas?anoLetivoId={ANO_LETIVO_ID}&greId={GRE_ID_3}&escolaId={escola_id_siage}&page=1&numPerPage=100"
            res_turmas = page.evaluate(script_js, {"url": url_turmas, "token": self.token})

            turmas_lista = []
            if isinstance(res_turmas, dict) and res_turmas.get("success"):
                data_obj = res_turmas.get("data") or {}
                turmas_obj = data_obj.get("turmas") or {}
                if isinstance(turmas_obj, dict):
                    turmas_lista = turmas_obj.get("data") or []
                elif isinstance(turmas_obj, list):
                    turmas_lista = turmas_obj

            for t in turmas_lista:
                if not isinstance(t, dict):
                    continue
                t['escolaId'] = escola_id_siage
                t['codigoInep'] = inep
                quadro_id = t.get('quadroId')
                formacao_turma_id = t.get('formacaoTurmaId') or t.get('id')

                if quadro_id and formacao_turma_id:
                    try:
                        t['detalhes_quadro'] = self._extrair_detalhes_quadro_planejamento(page, quadro_id, formacao_turma_id)
                    except Exception:
                        t['detalhes_quadro'] = None

                todos_planejamentos.append(t)

        return todos_planejamentos

    def _extrair_profissionais_por_escolas(self, page, escolas_api):
        script_js = """
        async ({ url, token }) => {
            let headers = { "Content-Type": "application/json" };
            if (token) headers["Authorization"] = token;
            try {
                const resp = await fetch(url, { headers: headers });
                let json = null;
                try { json = await resp.json(); } catch(e) {}
                return { status: resp.status, data: json };
            } catch (e) {
                return { status: 500, error: e.toString() };
            }
        }
        """
        todos_profissionais = []
        for escola in escolas_api:
            if not isinstance(escola, dict):
                continue
            escola_id = str(escola.get('id') or escola.get('escolaId') or escola.get('value') or '').strip()
            inep_escola = str(escola.get('codigoInep') or escola.get('inep') or escola.get('codigo') or '').strip()

            if not escola_id:
                continue

            pagina = 1
            while True:
                url_prof = (
                    f"{API_HOST}/Profissional/?"
                    f"page={pagina}&numPerPage=100"
                    f"&limitarQuantidadePagina=true&quantidadeRegistro=600"
                    f"&chegouUltimaPagina=false"
                    f"&anoLetivoId={ANO_LETIVO_ID}"
                    f"&greId={GRE_ID_3}"
                    f"&escolaId={escola_id}"
                )
                res = page.evaluate(script_js, {"url": url_prof, "token": self.token})
                status = res.get("status")
                dados = res.get("data")

                if status != 200 or not dados:
                    break

                itens = extrair_lista_generica(dados)
                if not itens:
                    break

                for item in itens:
                    if isinstance(item, dict):
                        if not item.get('escolaId'):
                            item['escolaId'] = escola_id
                        if not item.get('codigoInep') and inep_escola:
                            item['codigoInep'] = inep_escola

                todos_profissionais.extend(itens)

                total_paginas = None
                if isinstance(dados, dict) and "data" in dados and isinstance(dados["data"], dict):
                    page_info = dados["data"].get("page", {})
                    if isinstance(page_info, dict):
                        total_paginas = page_info.get("pageCount")

                if total_paginas and pagina >= total_paginas:
                    break

                chegou_fim = dados.get("chegouUltimaPagina", False) if isinstance(dados, dict) else False
                if chegou_fim or len(itens) < 100:
                    break

                pagina += 1
                time.sleep(0.05)

        return todos_profissionais

    def _recuperar_cpfs_em_lotes(self, page, lista_profissionais, tamanho_lote=10):
        cpfs_ja_salvos = {}
        try:
            profs = db.session.query(Professor).all()
            for p in profs:
                if p.cpf and not cpf_eh_invalido_ou_vazio(p.cpf):
                    if p.matricula:
                        cpfs_ja_salvos[p.matricula.strip()] = p.cpf.strip()
                    if p.nome:
                        cpfs_ja_salvos[p.nome.strip().upper()] = p.cpf.strip()
        except Exception:
            db.session.rollback()

        itens_para_buscar = []
        for idx, p in enumerate(lista_profissionais):
            if not isinstance(p, dict):
                continue

            mat = str(p.get('matricula') or '').strip()
            nome = str(p.get('servidor') or p.get('nome') or '').strip().upper()
            cpf_existente = cpfs_ja_salvos.get(mat) or cpfs_ja_salvos.get(nome)

            if cpf_existente:
                p['cpf'] = cpf_existente
            else:
                p['_idx'] = idx
                itens_para_buscar.append({
                    '_idx': idx,
                    'id': p.get('id') or p.get('profissionalId') or p.get('cursoId'),
                    'servidor': p.get('servidor') or p.get('nome') or p.get('nomeServidor') or '',
                    'matricula': mat,
                    'nomeEscola': p.get('nomeEscola') or p.get('unidadeEscolar') or '',
                    'cursoId': p.get('cursoId'),
                    'tipoFormacao': p.get('tipoFormacao') or ''
                })

        if not itens_para_buscar:
            return

        script_lote_js = """
        async ({ chunk, token, apiHost }) => {
            let headers = { "Content-Type": "application/json", "Accept": "application/json" };
            if (token) headers["Authorization"] = token;

            async function consultarComRetentativa(item) {
                let profId = item.id || item.cursoId;
                if (!profId) return { idx: item._idx, cpf: null };

                let servidor = encodeURIComponent(item.servidor || '');
                let matricula = encodeURIComponent(item.matricula || '');
                let nomeEscola = encodeURIComponent(item.nomeEscola || '');
                let cursoId = encodeURIComponent(item.cursoId || profId);

                let urls = [
                    `${apiHost}/Profissional/${profId}/`,
                    `${apiHost}/Profissional/${profId}/?page=1&numPerPage=50&limitarQuantidadePagina=false&chegouUltimaPagina=false&cursoId=${cursoId}&servidor=${servidor}&matricula=${matricula}&nomeEscola=${nomeEscola}`,
                    `${apiHost}/Profissional/${profId}/?tipoFormacao=CURSO_SUPERIOR`,
                    `${apiHost}/Profissional/${profId}/?tipoFormacao=POS_GRADUACAO`
                ];

                for (let url of urls) {
                    try {
                        let resp = await fetch(url, { headers: headers });
                        if (resp.status === 200) {
                            let json = await resp.json();
                            let objData = json.data || json;
                            let cpfEncontrado = objData.cpf || objData.numCpf || objData.cpfServidor || objData.cpfProfissional;

                            if (cpfEncontrado) {
                                return { idx: item._idx, cpf: String(cpfEncontrado).trim() };
                            }

                            let jsonStr = JSON.stringify(json);
                            let match = jsonStr.match(/"(?:cpf|cpfServidor|numCpf|documento)"\\s*:\\s*"(\\d{11}|\\d{3}\\.\\d{3}\\.\\d{3}-\\d{2})"/i);
                            if (match && match[1]) {
                                return { idx: item._idx, cpf: match[1] };
                            }
                        }
                    } catch(e) {}
                }
                return { idx: item._idx, cpf: null };
            }

            const resultados = await Promise.all(chunk.map(it => consultarComRetentativa(it)));
            let mapa = {};
            for (let r of resultados) {
                if (r && r.cpf) mapa[r.idx] = r.cpf;
            }
            return mapa;
        }
        """

        total_lotes = (len(itens_para_buscar) + tamanho_lote - 1) // tamanho_lote
        for lote_num in range(total_lotes):
            inicio = lote_num * tamanho_lote
            fim = inicio + tamanho_lote
            chunk = itens_para_buscar[inicio:fim]

            res_mapa = page.evaluate(script_lote_js, {
                "chunk": chunk,
                "token": self.token,
                "apiHost": API_HOST
            })

            if isinstance(res_mapa, dict):
                for idx_str, raw_cpf in res_mapa.items():
                    try:
                        i = int(idx_str)
                        cpf_fmt = formatar_cpf(raw_cpf)
                        if cpf_fmt:
                            lista_profissionais[i]['cpf'] = cpf_fmt
                    except (ValueError, IndexError):
                        pass
            time.sleep(0.05)

    # =========================================================================
    # PERSISTÊNCIA NO POSTGRESQL
    # =========================================================================

    def _sincronizar_escolas_no_postgres(self, escolas_api):
        mapa_escolas = {}
        novas_escolas = 0

        for esc in escolas_api:
            if not isinstance(esc, dict):
                continue

            siage_id = str(esc.get('id') or esc.get('escolaId') or esc.get('value') or '').strip()
            nome = str(esc.get('nome') or esc.get('nomeEscola') or esc.get('text') or esc.get('label') or '').strip().upper()
            inep = str(esc.get('codigoInep') or esc.get('inep') or esc.get('codigo') or '').strip()
            inep_clean = inep.lstrip('0')

            if not nome and not inep:
                continue

            escola_db_id = None

            if inep_clean:
                try:
                    sql_chk = db.text("SELECT id FROM escola WHERE LTRIM(TRIM(CAST(inep_visual AS VARCHAR)), '0') = :clean LIMIT 1")
                    row = db.session.execute(sql_chk, {"clean": inep_clean}).fetchone()
                    if row:
                        escola_db_id = row[0]
                except Exception:
                    db.session.rollback()

            if not escola_db_id and nome:
                try:
                    sql_nome = db.text("SELECT id FROM escola WHERE UPPER(TRIM(nome)) = :nome LIMIT 1")
                    row = db.session.execute(sql_nome, {"nome": nome}).fetchone()
                    if row:
                        escola_db_id = row[0]
                except Exception:
                    db.session.rollback()

            if not escola_db_id and (inep or nome):
                try:
                    sql_ins = db.text("INSERT INTO escola (inep_visual, nome) VALUES (:inep, :nome) RETURNING id")
                    res_ins = db.session.execute(sql_ins, {"inep": inep or "0", "nome": nome or "ESCOLA"}).fetchone()
                    if res_ins:
                        escola_db_id = res_ins[0]
                        novas_escolas += 1
                except Exception:
                    db.session.rollback()

            if escola_db_id:
                if inep:
                    mapa_escolas[inep] = escola_db_id
                    mapa_escolas[inep_clean] = escola_db_id
                if siage_id:
                    mapa_escolas[siage_id] = escola_db_id
                mapa_escolas[str(escola_db_id)] = escola_db_id

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        return mapa_escolas

    def _salvar_planejamento_turmas_no_postgres(self, mapa_escolas, planejamentos_lista, ano_letivo=ANO_LETIVO_NUMERO):
        if not planejamentos_lista:
            return

        MAPA_AREAS = {
            "PORTUGUÊS": "LÍNGUA PORTUGUESA", "PORTUGUES": "LÍNGUA PORTUGUESA", "LÍNGUA PORTUGUESA": "LÍNGUA PORTUGUESA",
            "MATEMÁTICA": "MATEMÁTICA", "MATEMATICA": "MATEMÁTICA", "BIOLOGIA": "BIOLOGIA", "FÍSICA": "FÍSICA",
            "FISICA": "FÍSICA", "QUÍMICA": "QUÍMICA", "QUIMICA": "QUÍMICA", "HISTÓRIA": "HISTÓRIA", "HISTORIA": "HISTÓRIA",
            "GEOGRAFIA": "GEOGRAFIA", "INGLÊS": "LÍNGUA ESTRANGEIRA - INGLÊS", "INGLES": "LÍNGUA ESTRANGEIRA - INGLÊS",
            "LÍNGUA INGLESA": "LÍNGUA ESTRANGEIRA - INGLÊS", "LÍNGUA ESPANHOLA": "LÍNGUA ESTRANGEIRA - INGLÊS",
            "ESPANHOL": "LÍNGUA ESTRANGEIRA - INGLÊS", "LÍNGUA ESTRANGEIRA": "LÍNGUA ESTRANGEIRA - INGLÊS",
            "LÍNGUA ESTRANGEIRA - INGLÊS": "LÍNGUA ESTRANGEIRA - INGLÊS", "EDUCAÇÃO FÍSICA": "EDUCAÇÃO FÍSICA",
            "EDUCACAO FISICA": "EDUCAÇÃO FÍSICA", "ARTE": "ARTE", "ARTES": "ARTE", "SOCIOLOGIA": "SOCIOLOGIA",
            "FILOSOFIA": "FILOSOFIA", "PROJETO DE VIDA": "PROJETO DE VIDA", "ELETIVAS": "ELETIVAS", "ELETIVA": "ELETIVAS",
            "ESTUDOS ORIENTADOS": "ESTUDOS ORIENTADOS"
        }

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
            """))
            db.session.commit()
        except Exception:
            db.session.rollback()

        for t in planejamentos_lista:
            if not isinstance(t, dict):
                continue

            inep = str(t.get('codigoInep') or t.get('inep') or '').strip()
            inep_clean = inep.lstrip('0')
            escola_id_siage = str(t.get('escolaId') or '').strip()
            escola_db_id = mapa_escolas.get(inep) or mapa_escolas.get(escola_id_siage) or mapa_escolas.get(inep_clean)

            if not escola_db_id:
                continue

            turno = str(t.get('turno') or 'INTEGRAL').strip().upper()
            etapa = str(t.get('etapa') or '').strip().upper()
            turma_nome = str(t.get('turma') or t.get('nomeTurma') or '').strip().upper()
            situacao = str(t.get('situacao') or 'APROVADO').strip().upper()

            detalhes = t.get('detalhes_quadro') or {}
            componentes = detalhes.get('componentes') if isinstance(detalhes, dict) else []

            if componentes and isinstance(componentes, list):
                for c in componentes:
                    if not isinstance(c, dict):
                        continue

                    raw_area = str(c.get('nomeComponente') or c.get('componenteCurricular') or c.get('disciplina') or '').strip().upper()
                    area_conhecimento = MAPA_AREAS.get(raw_area)
                    if not area_conhecimento:
                        for chave_mapa, area_padrao in MAPA_AREAS.items():
                            if chave_mapa in raw_area:
                                area_conhecimento = area_padrao
                                break

                    if not area_conhecimento:
                        area_conhecimento = raw_area or 'COMPONENTE CURRICULAR'

                    responsavel = str(c.get('nomeProfessor') or c.get('servidor') or c.get('docente') or c.get('responsavel') or '').strip().upper()
                    dia_semana = normalizar_dia_semana(c.get('diaSemana') or c.get('dia') or '')
                    h_ini = normalizar_horario(c.get('horarioInicio') or c.get('horaInicio') or '')
                    h_fim = normalizar_horario(c.get('horarioFim') or c.get('horaFim') or '')
                    turno_comp = str(c.get('turno') or turno).strip().upper()
                    obs = f"SIAGE: {turma_nome} ({etapa}) - STATUS: {situacao}"

                    try:
                        sql_find = db.text("""
                            SELECT id FROM planejamento 
                            WHERE COALESCE(ano_letivo, '2026') = :ano
                              AND (UPPER(TRIM(area_conhecimento)) = :area OR UPPER(TRIM(area_conhecimento)) LIKE :area_like)
                              AND (escola_id = :e_id OR LTRIM(TRIM(CAST(COALESCE(codigo_inep, '') AS VARCHAR)), '0') = :clean)
                            LIMIT 1
                        """)
                        row = db.session.execute(sql_find, {
                            "ano": ano_letivo,
                            "area": area_conhecimento,
                            "area_like": f"%{area_conhecimento}%",
                            "e_id": escola_db_id,
                            "clean": inep_clean
                        }).fetchone()

                        if row:
                            sql_upd = db.text("""
                                UPDATE planejamento 
                                SET dia_semana = COALESCE(NULLIF(:dia, ''), dia_semana),
                                    horario_inicio = COALESCE(NULLIF(:h_ini, ''), horario_inicio),
                                    horario_fim = COALESCE(NULLIF(:h_fim, ''), horario_fim),
                                    turno = COALESCE(NULLIF(:turno, ''), turno),
                                    responsavel = COALESCE(NULLIF(:resp, ''), responsavel),
                                    turma_nome = COALESCE(NULLIF(:turma, ''), turma_nome),
                                    observacao = :obs
                                WHERE id = :id
                            """)
                            db.session.execute(sql_upd, {
                                "id": row[0], "dia": dia_semana, "h_ini": h_ini, "h_fim": h_fim,
                                "turno": turno_comp, "resp": responsavel, "turma": turma_nome, "obs": obs
                            })
                        else:
                            sql_ins = db.text("""
                                INSERT INTO planejamento (
                                    escola_id, codigo_inep, ano_letivo, area_conhecimento, turma_nome,
                                    dia_semana, horario_inicio, horario_fim, turno, responsavel, observacao
                                ) VALUES (
                                    :e_id, :inep, :ano, :area, :turma, :dia, :h_ini, :h_fim, :turno, :resp, :obs
                                )
                            """)
                            db.session.execute(sql_ins, {
                                "e_id": escola_db_id, "inep": inep_clean, "ano": ano_letivo,
                                "area": area_conhecimento, "turma": turma_nome, "dia": dia_semana,
                                "h_ini": h_ini, "h_fim": h_fim, "turno": turno_comp, "resp": responsavel, "obs": obs
                            })
                    except Exception:
                        db.session.rollback()

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    def _mapear_campos_professor_incremental(self, prof_obj, p_dict, escola_db_id, ano_letivo=ANO_LETIVO_NUMERO):
        def definir_se_vazio(atributo, novo_valor):
            if not hasattr(prof_obj, atributo):
                return
            valor_atual = getattr(prof_obj, atributo, None)
            if valor_eh_vazio(valor_atual):
                if not valor_eh_vazio(novo_valor):
                    setattr(prof_obj, atributo, novo_valor)

        cpf = formatar_cpf(p_dict.get('cpf'))
        matricula = str(p_dict.get('matricula') or p_dict.get('id') or p_dict.get('profissionalId') or '').strip()

        if valor_eh_vazio(matricula):
            if cpf and not cpf_eh_invalido_ou_vazio(cpf):
                digits_cpf = ''.join(c for c in cpf if c.isdigit())
                matricula = f"CPF-{digits_cpf}"
            else:
                prof_id = str(p_dict.get('id') or p_dict.get('profissionalId') or p_dict.get('cursoId') or '').strip()
                if prof_id and prof_id != 'None':
                    matricula = f"SIAGE-{prof_id}"
                else:
                    matricula = f"TEMP-{int(time.time()*1000)}"

        nome = str(p_dict.get('servidor') or p_dict.get('nome') or p_dict.get('nomeServidor') or '').strip().upper()
        vinculo = str(p_dict.get('vinculo') or p_dict.get('cargo') or p_dict.get('funcao') or 'EFETIVO').strip().upper()
        situacao = str(p_dict.get('situacao') or p_dict.get('status') or 'APROVADO').strip().upper()
        inep = str(p_dict.get('codigoInep') or p_dict.get('inep') or '').strip().lstrip('0')
        formacao = str(p_dict.get('formacao') or p_dict.get('tipoFormacao') or '').strip()

        ch_raw = p_dict.get('cargaHorariaOriginal') or p_dict.get('cargaHoraria')
        try:
            ch_original = float(ch_raw) if ch_raw else 40.0
        except (ValueError, TypeError):
            ch_original = 40.0

        if getattr(prof_obj, 'escola_id', None) is None:
            setattr(prof_obj, 'escola_id', escola_db_id)

        if hasattr(prof_obj, 'matricula') and valor_eh_vazio(getattr(prof_obj, 'matricula', None)):
            setattr(prof_obj, 'matricula', matricula)

        if cpf and hasattr(prof_obj, 'cpf'):
            if cpf_eh_invalido_ou_vazio(getattr(prof_obj, 'cpf', None)):
                setattr(prof_obj, 'cpf', cpf)

        if nome and hasattr(prof_obj, 'nome'):
            if valor_eh_vazio(getattr(prof_obj, 'nome', None)):
                setattr(prof_obj, 'nome', nome)

        definir_se_vazio('vinculo', vinculo)
        definir_se_vazio('escola_inep', inep)
        definir_se_vazio('utb_esta_escola', 'SIM')
        definir_se_vazio('forma_atuacao', 'CUMPRE INTEGRALMENTE A CH NESTA UNIDADE')

        if hasattr(prof_obj, 'carga_horaria_original'):
            if getattr(prof_obj, 'carga_horaria_original', None) is None or getattr(prof_obj, 'carga_horaria_original', 0) == 0:
                setattr(prof_obj, 'carga_horaria_original', ch_original)

        definir_se_vazio('possui_ch_fora', 'NÃO')
        if hasattr(prof_obj, 'ch_fora'):
            if getattr(prof_obj, 'ch_fora', None) is None:
                setattr(prof_obj, 'ch_fora', 0.0)

        definir_se_vazio('conselho_escolar', 'NÃO PARTICIPA')
        definir_se_vazio('areas_planejamento', 'LINGUAGENS')
        definir_se_vazio('reducao_legal_vigente', 'NÃO')

        if hasattr(prof_obj, 'carga_horaria_autorizada'):
            if getattr(prof_obj, 'carga_horaria_autorizada', None) is None or getattr(prof_obj, 'carga_horaria_autorizada', 0) == 0:
                setattr(prof_obj, 'carga_horaria_autorizada', ch_original)

        if hasattr(prof_obj, 'regencia_autorizada'):
            if getattr(prof_obj, 'regencia_autorizada', None) is None:
                setattr(prof_obj, 'regencia_autorizada', 0.0)

        definir_se_vazio('situacao_cadastro', 'SIM' if situacao in ['APROVADO', 'SIM', 'ATIVO'] else 'SITUAÇÃO A VERIFICAR')

        obs_texto = f"SIAGE {ano_letivo}: {situacao}" + (f" | {formacao}" if formacao else "")
        definir_se_vazio('observacoes', obs_texto)

    def _salvar_professores_no_postgres(self, lista_profissionais, mapa_escolas, ano_letivo=ANO_LETIVO_NUMERO):
        if not Professor or not lista_profissionais:
            return 0

        adicionados = 0
        atualizados = 0

        try:
            profs_existentes = db.session.query(Professor).all()
        except Exception:
            db.session.rollback()
            profs_existentes = []

        mapa_por_cpf = {p.cpf.strip(): p for p in profs_existentes if getattr(p, 'cpf', None) and not cpf_eh_invalido_ou_vazio(p.cpf)}
        mapa_por_mat = {p.matricula.strip(): p for p in profs_existentes if getattr(p, 'matricula', None) and str(p.matricula).strip()}
        mapa_por_nome_escola = {(p.nome.strip().upper(), p.escola_id): p for p in profs_existentes if getattr(p, 'nome', None) and getattr(p, 'escola_id', None)}

        with db.session.no_autoflush:
            for idx, p in enumerate(lista_profissionais, 1):
                if not isinstance(p, dict):
                    continue

                matricula = str(p.get('matricula') or p.get('id') or p.get('profissionalId') or '').strip()
                cpf_lista = formatar_cpf(p.get('cpf'))
                nome = str(p.get('servidor') or p.get('nome') or p.get('nomeServidor') or '').strip().upper()

                escola_id_siage = str(p.get('escolaId') or p.get('escola_id') or '').strip()
                inep = str(p.get('codigoInep') or p.get('inep') or '').strip()
                inep_clean = inep.lstrip('0')

                if not nome or nome == 'NONE':
                    continue

                escola_db_id = mapa_escolas.get(inep) or mapa_escolas.get(escola_id_siage) or mapa_escolas.get(inep_clean)
                if not escola_db_id:
                    continue

                prof_obj = None
                if cpf_lista and cpf_lista in mapa_por_cpf:
                    prof_obj = mapa_por_cpf[cpf_lista]
                elif matricula and matricula != "000.000-0" and matricula in mapa_por_mat:
                    prof_obj = mapa_por_mat[matricula]
                elif (nome, escola_db_id) in mapa_por_nome_escola:
                    prof_obj = mapa_por_nome_escola[(nome, escola_db_id)]

                if prof_obj:
                    self._mapear_campos_professor_incremental(prof_obj, p, escola_db_id, ano_letivo)
                    atualizados += 1
                else:
                    prof_obj = Professor()
                    self._mapear_campos_professor_incremental(prof_obj, p, escola_db_id, ano_letivo)
                    db.session.add(prof_obj)

                    cpf_final = getattr(prof_obj, 'cpf', None)
                    if cpf_final and not cpf_eh_invalido_ou_vazio(cpf_final):
                        mapa_por_cpf[cpf_final] = prof_obj
                    mat_final = getattr(prof_obj, 'matricula', None)
                    if mat_final:
                        mapa_por_mat[mat_final] = prof_obj
                    mapa_por_nome_escola[(nome, escola_db_id)] = prof_obj
                    adicionados += 1

                if idx % 200 == 0:
                    try:
                        db.session.commit()
                    except Exception:
                        db.session.rollback()

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        return adicionados + atualizados

    def _sincronizar_atuacao_professores_no_postgres(self, mapa_escolas=None, planejamentos_lista=None, profissionais_lista=None, ano_letivo=ANO_LETIVO_NUMERO):
        MAPA_AREAS_ATUACAO = {
            "PORTUGUÊS": "LINGUAGENS", "LÍNGUA PORTUGUESA": "LINGUAGENS", "ARTE": "LINGUAGENS", "ARTES": "LINGUAGENS",
            "EDUCAÇÃO FÍSICA": "LINGUAGENS", "LÍNGUA ESTRANGEIRA": "LINGUAGENS", "LÍNGUA INGLESA": "LINGUAGENS",
            "INGLÊS": "LINGUAGENS", "LÍNGUA ESPANHOLA": "LINGUAGENS", "ESPANHOL": "LINGUAGENS",
            "MATEMÁTICA": "MATEMÁTICA",
            "BIOLOGIA": "CIÊNCIAS DA NATUREZA", "FÍSICA": "CIÊNCIAS DA NATUREZA", "QUÍMICA": "CIÊNCIAS DA NATUREZA",
            "HISTÓRIA": "CIÊNCIAS HUMANAS", "GEOGRAFIA": "CIÊNCIAS HUMANAS", "SOCIOLOGIA": "CIÊNCIAS HUMANAS", "FILOSOFIA": "CIÊNCIAS HUMANAS"
        }

        try:
            db.session.execute(db.text("""
                CREATE TABLE IF NOT EXISTS atuacao (
                    id SERIAL PRIMARY KEY,
                    escola_id INT,
                    codigo_inep VARCHAR(20),
                    ano_letivo VARCHAR(10),
                    matricula VARCHAR(50),
                    professor_nome VARCHAR(150),
                    atividade_componente VARCHAR(150),
                    turno VARCHAR(50),
                    etapa_modalidade VARCHAR(100),
                    area VARCHAR(100),
                    ch_semanal FLOAT DEFAULT 0,
                    turmas_atendidas VARCHAR(255),
                    dias_atuacao VARCHAR(255),
                    situacao_preenchimento VARCHAR(50) DEFAULT 'COMPLETO',
                    situacao_normativa VARCHAR(50) DEFAULT 'CONFORME',
                    grupo_atuacao VARCHAR(100) DEFAULT 'COMPONENTE CURRICULAR',
                    natureza_ch VARCHAR(100) DEFAULT 'INTERAÇÃO PEDAGÓGICA',
                    impacta_matriz VARCHAR(10) DEFAULT 'SIM',
                    compoe_bloco_regencia VARCHAR(10) DEFAULT 'SIM',
                    limite_regra VARCHAR(255) DEFAULT 'CONFORME MATRIZ CURRICULAR HOMOLOGADA',
                    base_normativa VARCHAR(255) DEFAULT 'PORTARIA Nº 028/2026/SEE-PB',
                    validacao_condicao VARCHAR(255) DEFAULT 'HABILITAÇÃO / PERFIL',
                    observacoes TEXT,
                    ch_autorizada FLOAT DEFAULT 40
                );
            """))
            db.session.commit()
        except Exception:
            db.session.rollback()

        sql_escola_plan = db.text("""
            SELECT 
                escola_id,
                STRING_AGG(DISTINCT NULLIF(TRIM(turma_nome), ''), ', ') as todas_turmas,
                STRING_AGG(DISTINCT NULLIF(TRIM(dia_semana), ''), ', ') as todos_dias
            FROM planejamento
            WHERE COALESCE(ano_letivo, '2026') = :ano
            GROUP BY escola_id
        """)
        res_escola_plan = db.session.execute(sql_escola_plan, {"ano": ano_letivo}).fetchall()
        mapa_escola_plan = {}
        for r in res_escola_plan:
            e_id, turmas_raw, dias_raw = r
            t_list = sorted(set(t.strip() for t in (turmas_raw or "").split(",") if t.strip()))
            d_list = sorted(set(d.strip() for d in (dias_raw or "").split(",") if d.strip()))
            mapa_escola_plan[e_id] = {
                'turmas': ", ".join(t_list) if t_list else "1º ANO A, 2º ANO A, 3º ANO A",
                'dias': ", ".join(d_list) if d_list else "SEGUNDA-FEIRA, TERÇA-FEIRA, QUARTA-FEIRA, QUINTA-FEIRA, SEXTA-FEIRA"
            }

        sql_resp_plan = db.text("""
            SELECT 
                escola_id,
                UPPER(TRIM(responsavel)) as professor,
                UPPER(TRIM(area_conhecimento)) as componente,
                STRING_AGG(DISTINCT NULLIF(TRIM(turma_nome), ''), ', ') as turmas,
                STRING_AGG(DISTINCT NULLIF(TRIM(dia_semana), ''), ', ') as dias
            FROM planejamento
            WHERE COALESCE(ano_letivo, '2026') = :ano
              AND responsavel IS NOT NULL 
              AND TRIM(responsavel) NOT IN ('', 'NONE', 'NULL', 'A DEFINIR')
            GROUP BY escola_id, UPPER(TRIM(responsavel)), UPPER(TRIM(area_conhecimento))
        """)
        res_resp_plan = db.session.execute(sql_resp_plan, {"ano": ano_letivo}).fetchall()
        mapa_prof_plan = {}
        for r in res_resp_plan:
            e_id, prof, comp, turmas_raw, dias_raw = r
            t_list = sorted(set(t.strip() for t in (turmas_raw or "").split(",") if t.strip()))
            d_list = sorted(set(d.strip() for d in (dias_raw or "").split(",") if d.strip()))
            mapa_prof_plan[(e_id, prof)] = {
                'componente': comp,
                'turmas': ", ".join(t_list),
                'dias': ", ".join(d_list)
            }

        sql_todas_atuacoes = db.text("""
            SELECT id, escola_id, UPPER(TRIM(professor_nome)) as prof, UPPER(TRIM(atividade_componente)) as comp
            FROM atuacao
            WHERE COALESCE(ano_letivo, '2026') = :ano
        """)
        linhas_atuacao = db.session.execute(sql_todas_atuacoes, {"ano": ano_letivo}).fetchall()

        tot_atualizados = 0
        for row in linhas_atuacao:
            a_id, e_id, prof_nome, comp_atuacao = row
            prof_data = mapa_prof_plan.get((e_id, prof_nome))
            esc_data = mapa_escola_plan.get(e_id, {
                'turmas': '1º ANO A, 2º ANO A, 3º ANO A',
                'dias': 'SEGUNDA-FEIRA, TERÇA-FEIRA, QUARTA-FEIRA, QUINTA-FEIRA, SEXTA-FEIRA'
            })

            if prof_data:
                turmas_final = prof_data['turmas'] or esc_data['turmas']
                dias_final = prof_data['dias'] or esc_data['dias']
                comp_final = prof_data['componente'] or comp_atuacao
            else:
                turmas_final = esc_data['turmas']
                dias_final = esc_data['dias']
                comp_final = comp_atuacao

            area_cat = "OUTRA"
            for k_map, v_map in MAPA_AREAS_ATUACAO.items():
                if k_map in comp_final or k_map in comp_atuacao:
                    area_cat = v_map
                    break
            if area_cat == "OUTRA" and ("EXTRACLASSE" in comp_atuacao or "FORA" in comp_atuacao):
                area_cat = "OUTRA"
            elif area_cat == "OUTRA":
                area_cat = "LINGUAGENS"

            sql_upd = db.text("""
                UPDATE atuacao 
                SET area = CASE WHEN area IS NULL OR TRIM(area) = '' THEN :area ELSE area END,
                    turmas_atendidas = CASE WHEN turmas_atendidas IS NULL OR TRIM(turmas_atendidas) = '' THEN :turmas ELSE turmas_atendidas END,
                    dias_atuacao = CASE WHEN dias_atuacao IS NULL OR TRIM(dias_atuacao) = '' THEN :dias ELSE dias_atuacao END,
                    atividade_componente = CASE WHEN atividade_componente = 'COMPONENTE CURRICULAR' AND :comp != 'COMPONENTE CURRICULAR' THEN :comp ELSE atividade_componente END
                WHERE id = :id
            """)
            db.session.execute(sql_upd, {
                "id": a_id,
                "area": area_cat,
                "turmas": turmas_final,
                "dias": dias_final,
                "comp": comp_final
            })
            tot_atualizados += 1

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        return tot_atualizados