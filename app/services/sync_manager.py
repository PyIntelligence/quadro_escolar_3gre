# app/services/sync_manager.py

import sys
import traceback

PROGRESSO_ATUAL = {
    "percentual": 0, 
    "status": "Aguardando início...", 
    "em_execucao": False,
    "erro": False
}

def atualizar_progresso(pct, msg, erro=False):
    global PROGRESSO_ATUAL
    PROGRESSO_ATUAL["percentual"] = pct
    PROGRESSO_ATUAL["status"] = msg
    PROGRESSO_ATUAL["erro"] = erro
    if erro:
        PROGRESSO_ATUAL["em_execucao"] = False
    else:
        PROGRESSO_ATUAL["em_execucao"] = True

    prefixo = "❌ ERRO" if erro else "INFO"
    print(f"[{prefixo}] [{pct}%] {msg}", flush=True)

def executar_sincronizacao_completa(url_google_sheets=None):
    global PROGRESSO_ATUAL
    PROGRESSO_ATUAL["em_execucao"] = True
    PROGRESSO_ATUAL["erro"] = False
    
    atualizar_progresso(2, "⚙️ Conectando ao banco de dados e preparando robô...")

    # 1. Execução no SIAGE
    try:
        from app.services.siage_smart_sync import RobosiageInteligente
        robô = RobosiageInteligente(callback_progresso=atualizar_progresso)
        sucesso_siage, msg_siage = robô.sincronizar_tudo_incremental()

        if not sucesso_siage:
            atualizar_progresso(0, f"❌ Falha no SIAGE: {msg_siage}", erro=True)
            return
    except Exception as e:
        tb = traceback.format_exc()
        print(f"\n[ERRO CRÍTICO NO SIAGE]\n{tb}", file=sys.stderr, flush=True)
        atualizar_progresso(0, f"❌ Erro na sincronização SIAGE: {str(e)}", erro=True)
        return

    # 2. Execução no Google Sheets (Opcional)
    if url_google_sheets and str(url_google_sheets).strip():
        try:
            from app.services.google_sheets_sync import sincronizar_via_google_sheets
            sincronizar_via_google_sheets(
                url_google_sheets, 
                callback_progresso=atualizar_progresso
            )
        except ImportError:
            print("[AVISO] Módulo google_sheets_sync não encontrado. Pulando etapa de Google Sheets.", flush=True)
        except Exception as e:
            print(f"[AVISO] Erro na sincronização do Google Sheets: {e}", flush=True)

    atualizar_progresso(100, "🎉 Sincronização concluída com sucesso!")
    PROGRESSO_ATUAL["em_execucao"] = False