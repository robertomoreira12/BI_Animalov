import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
import json
import tempfile
import os
import base64

# Configuração da Página
st.set_page_config(page_title="Animalov - BI Histórico & Comparativo", page_icon="🐾", layout="wide")

st.title("🐾 Animalov - Central de BI & Inteligência Financeira")

# Ligação com Google Sheets via Base64 e Gestão de Abas
@st.cache_resource
def ligar_google_sheets():
    base64_creds = st.secrets["GCP_JSON_BASE64"]
    json_bytes = base64.b64decode(base64_creds)
    credenciais_dict = json.loads(json_bytes.decode('utf-8'))

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8') as f:
        json.dump(credenciais_dict, f)
        temp_path = f.name

    try:
        gc = gspread.service_account(filename=temp_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    id_planilha = "13gngB_axx-1L__qqoA2PGUXFp9XVexJA_zYQADUNOtQ"
    sh = gc.open_by_key(id_planilha)
    
    # Aba 1: Histórico de Vendas
    try:
        ws_hist = sh.worksheet('Historico_Vendas')
    except gspread.exceptions.WorksheetNotFound:
        ws_hist = sh.add_worksheet(title='Historico_Vendas', rows=1000, cols=20)
        ws_hist.append_row([
            'Mes_Ano', 'Data_Hora', 'Departamento', 'Líquido', 'Bruto', 
            'Grupo', 'Tipo_Item'
        ])
        
    # Aba 2: Histórico de Contas Pagas (Custos)
    try:
        ws_contas = sh.worksheet('Contas_Pagas')
    except gspread.exceptions.WorksheetNotFound:
        ws_contas = sh.add_worksheet(title='Contas_Pagas', rows=100, cols=5)
        ws_contas.append_row(['Mes_Ano', 'Valor_Contas_Pagas'])
        
    return ws_hist, ws_contas

try:
    ws_historico, ws_contas_pagas = ligar_google_sheets()
except Exception as e:
    st.error(f"Erro ao ligar com a base do Google Sheets: {e}")
    st.stop()

# ==========================================
# FUNÇÕES DE LEITURA INTELIGENTE E ROBUSTA
# ==========================================
def carregar_dados_vendas(ws):
    dados = ws.get_all_values()
    colunas_padrao = ['Mes_Ano', 'Data_Hora', 'Departamento', 'Líquido', 'Bruto', 'Grupo', 'Tipo_Item']
    
    if len(dados) <= 1:
        return pd.DataFrame(columns=colunas_padrao)
    
    header = [str(c).strip() for c in dados[0]]
    rows = dados[1:]
    
    linhas_normalizadas = []
    for r in rows:
        if len(r) < len(header):
            r = r + [''] * (len(header) - len(r))
        elif len(r) > len(header):
            r = r[:len(header)]
        linhas_normalizadas.append(r)
        
    df = pd.DataFrame(linhas_normalizadas, columns=header)
    
    for col in colunas_padrao:
        if col not in df.columns:
            df[col] = 'N/A'
            
    for col in ['Líquido', 'Bruto']:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace('R$', '', regex=False)
                .str.replace('.', '', regex=False)
                .str.replace(',', '.', regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
    return df

def carregar_dados_contas(ws):
    dados = ws.get_all_values()
    colunas_padrao = ['Mes_Ano', 'Valor_Contas_Pagas']
    
    if len(dados) <= 1:
        return pd.DataFrame(columns=colunas_padrao)
    
    header = [str(c).strip() for c in dados[0]]
    rows = dados[1:]
    
    linhas_normalizadas = []
    for r in rows:
        if len(r) < len(header):
            r = r + [''] * (len(header) - len(r))
        elif len(r) > len(header):
            r = r[:len(header)]
        linhas_normalizadas.append(r)
        
    df = pd.DataFrame(linhas_normalizadas, columns=header)
    
    for col in colunas_padrao:
        if col not in df.columns:
            df[col] = 0.0
            
    if 'Valor_Contas_Pagas' in df.columns:
        df['Valor_Contas_Pagas'] = (
            df['Valor_Contas_Pagas'].astype(str)
            .str.replace('R$', '', regex=False)
            .str.replace('.', '', regex=False)
            .str.replace(',', '.', regex=False)
            .str.strip()
        )
        df['Valor_Contas_Pagas'] = pd.to_numeric(df['Valor_Contas_Pagas'], errors='coerce').fillna(0.0)
    else:
        df['Valor_Contas_Pagas'] = 0.0
        
    return df

# ==========================================
# SIDEBAR - CARREGAMENTO / REGISTRO COM RAIO-X
# ==========================================
st.sidebar.header("📥 Registar Novo Mês no Histórico")

with st.sidebar.expander("Upload de Dados (Simplesvet)"):
    uploaded_file = st.file_uploader("Enviar CSV do Simplesvet", type=["csv"])
    
    if uploaded_file:
        try:
            df_temp = pd.read_csv(uploaded_file, sep=';', encoding='latin1', on_bad_lines='skip')
        except Exception:
            uploaded_file.seek(0)
            df_temp = pd.read_csv(uploaded_file, sep=',', encoding='utf-8', on_bad_lines='skip')

        # RAIO-X DO CSV
        st.write("🔍 **Colunas detetadas no seu CSV:**", list(df_temp.columns))
        st.dataframe(df_temp.head(2))

        # Identifica dinamicamente a coluna de data
        coluna_data_csv = None
        for cand in ['Data e hora', 'Data', 'Data/Hora', 'Data da venda', 'Data/hora']:
            if cand in df_temp.columns:
                coluna_data_csv = cand
                break
                
        if coluna_data_csv is None and len(df_temp.columns) > 0:
            coluna_data_csv = df_temp.columns[0]
            
        if coluna_data_csv:
            df_temp['Data_Hora'] = pd.to_datetime(df_temp[coluna_data_csv], errors='coerce', dayfirst=True)
            df_temp['Mes_Ano'] = df_temp['Data_Hora'].dt.strftime('%m/%Y')
            
            meses_no_csv = df_temp['Mes_Ano'].dropna().unique().tolist()
            st.info(f"📅 Meses detetados no CSV: **{', '.join(meses_no_csv)}**")
        else:
            st.error("⚠️ Não foi possível identificar nenhuma coluna de data no CSV.")
        
        if st.button("💾 Guardar/Atualizar no Google Sheets"):
            with st.spinner("A processar e a guardar na base histórica..."):
                df_new = df_temp.copy()
                
                for col in ['Líquido', 'Bruto']:
                    if col in df_new.columns:
                        df_new[col] = (
                            df_new[col].astype(str)
                            .str.replace('R$', '', regex=False)
                            .str.replace('.', '', regex=False)
                            .str.replace(',', '.', regex=False)
                            .str.strip()
                        )
                        df_new[col] = pd.to_numeric(df_new[col], errors='coerce').fillna(0.0)

                def classificar_departamento(row):
                    grupo = str(row.get('Grupo', ''))
                    tipo = str(row.get('Tipo do Item', ''))
                    
                    if grupo == 'Farmácia': return 'Farmácia (Medicamentos)'
                    if tipo == 'Produto': return 'Petshop (Produtos)'
                    if grupo in ['Banho', 'Tosa', 'Hidratação', 'Desembolo', 'Corte de Unhas', 'Higiene e Beleza']: return 'Estética Pet'
                    if grupo in ['Consultas', 'Vacinas', 'Cirurgias', 'Exames', 'Procedimentos'] or tipo == 'Procedimento Petlove': return 'Clínica Veterinária'
                    if grupo == 'Transporte': return 'Táxi Pet'
                    if grupo == 'Hospedagem': return 'Creche & Hotel'
                    return 'Outros'

                df_new['Departamento'] = df_new.apply(classificar_departamento, axis=1)
                
                df_salvar = pd.DataFrame({
                    'Mes_Ano': df_new['Mes_Ano'],
                    'Data_Hora': df_new['Data_Hora'].dt.strftime('%Y-%m-%d %H:%M'),
                    'Departamento': df_new['Departamento'],
                    'Líquido': df_new.get('Líquido', 0),
                    'Bruto': df_new.get('Bruto', 0),
                    'Grupo': df_new.get('Grupo', 'N/A').fillna('N/A'),
                    'Tipo_Item': df_new.get('Tipo do Item', 'N/A').fillna('N/A')
                }).dropna(subset=['Mes_Ano'])

                df_existente = carregar_dados_vendas(ws_historico)
                if not df_existente.empty and 'Mes_Ano' in df_existente.columns:
                    df_existente = df_existente[~df_existente['Mes_Ano'].isin(meses_no_csv)]
                    df_final_base = pd.concat([df_existente, df_salvar], ignore_index=True)
                else:
                    df_final_base = df_salvar

                ws_historico.clear()
                ws_historico.update([df_final_base.columns.values.tolist()] + df_final_base.values.tolist())
                st.success(f"Dados atualizados com sucesso para os meses: {', '.join(meses_no_csv)}!")
                st.rerun()

# ==========================================
# CARREGAMENTO DA BASE HISTÓRICA COMPLETA
# ==========================================
df_historico = carregar_dados_vendas(ws_historico)
df_contas_historico = carregar_dados_contas(ws_contas_pagas)

if df_historico.empty or df_historico['Líquido'].sum() == 0:
    st.info("ℹ️ A base de dados de vendas no Google Sheets está vazia. Use o painel lateral para enviar o primeiro CSV do Simplesvet.")
    st.stop()

# Ordena os meses cronologicamente de forma correta
meses_disponiveis = sorted(
    [m for m in df_historico['Mes_Ano'].unique().tolist() if pd.notna(m) and m != 'N/A' and m != ''],
    key=lambda x: pd.to_datetime(x, format='%m/%Y', errors='coerce')
)

if not meses_disponiveis:
    st.error("⚠️ Não foram encontrados meses válidos na coluna 'Mes_Ano' do Google Sheets.")
    st.stop()

def obter_contas_mes(mes):
    match = df_contas_historico[df_contas_historico['Mes_Ano'] == mes]
    if not match.empty:
        val = match['Valor_Contas_Pagas'].values[0]
        return float(val) if pd.notna(val) else 0.0
    return 0.0

# ==========================================
# NAVEGAÇÃO E ANÁLISE NO STREAMLIT
# ==========================================
st.sidebar.divider()
modo_analise = st.sidebar.radio("🔍
