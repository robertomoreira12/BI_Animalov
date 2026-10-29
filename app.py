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
colunas_padrao = ['Mes_Ano', 'Data_Hora', 'Departamento', 'Líquido', 'Bruto', 'Grupo', 'Tipo_Item']

def carregar_dados_vendas(ws):
    dados = ws.get_all_values()
    
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
    df = df.loc[:, ~df.columns.duplicated()]
    
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
            
    return df[colunas_padrao]

def carregar_dados_contas(ws):
    dados = ws.get_all_values()
    cols_contas = ['Mes_Ano', 'Valor_Contas_Pagas']
    
    if len(dados) <= 1:
        return pd.DataFrame(columns=cols_contas)
    
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
    df = df.loc[:, ~df.columns.duplicated()]
    
    for col in cols_contas:
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
        
    return df[cols_contas]

# ==========================================
# SIDEBAR - CARREGAMENTO / REGISTRO COM RAIO-X ABERTO
# ==========================================
st.sidebar.header("📥 Registar Novo Mês no Histórico")

with st.sidebar.expander("Upload de Dados (Simplesvet)", expanded=True):
    uploaded_file = st.file_uploader("Enviar CSV do Simplesvet", type=["csv"])
    
    if uploaded_file:
        try:
            df_temp = pd.read_csv(uploaded_file, sep=';', encoding='latin1', on_bad_lines='skip')
        except Exception:
            uploaded_file.seek(0)
            df_temp = pd.read_csv(uploaded_file, sep=',', encoding='utf-8', on_bad_lines='skip')

        st.write("🔍 **Colunas detetadas no seu CSV:**", list(df_temp.columns))
        st.dataframe(df_temp.head(2))

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

                # Seleção estrita das colunas padrão para prevenir duplicados ou conflitos de índice
                df_salvar = df_salvar[colunas_padrao]

                df_existente = carregar_dados_vendas(ws_historico)
                if not df_existente.empty and 'Mes_Ano' in df_existente.columns:
                    df_existente = df_existente[~df_existente['Mes_Ano'].isin(meses_no_csv)]
                    df_existente = df_existente[colunas_padrao]
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
    st.info("ℹ️ A base de dados de vendas no Google Sheets está vazia. Use o painel lateral à esquerda para enviar o seu primeiro ficheiro CSV do Simplesvet.")
    st.stop()

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
modo_analise = st.sidebar.radio("🔍 Modo de Análise", ["Mês Individual", "Comparativo Entre Meses", "Visão Geral do Histórico"])

def calcular_resumo(mes_sel):
    df_filtrado = df_historico[df_historico['Mes_Ano'] == mes_sel]
    contas_pagas = obter_contas_mes(mes_sel)
    fat_total = df_filtrado['Líquido'].sum()
    
    resumo = df_filtrado.groupby('Departamento')['Líquido'].sum().reset_index()
    resumo.rename(columns={'Líquido': 'Faturamento'}, inplace=True)
    resumo['% Share'] = resumo['Faturamento'] / fat_total if fat_total > 0 else 0
    resumo['Custo Rateado'] = resumo['% Share'] * contas_pagas
    resumo['Resultado Líquido'] = resumo['Faturamento'] - resumo['Custo Rateado']
    resumo['Margem %'] = resumo['Resultado Líquido'] / resumo['Faturamento']
    return resumo, fat_total, contas_pagas

# 1. MÊS INDIVIDUAL
if modo_analise == "Mês Individual":
    mes_sel = st.selectbox("Selecione o Mês para Análise:", meses_disponiveis, index=len(meses_disponiveis)-1)
    
    resumo, fat_total, contas_pagas = calcular_resumo(mes_sel)
    
    st.subheader(f"📊 Relatório Financeiro: {mes_sel}")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Faturamento Total", f"R$ {fat_total:,.2f}")
    c2.metric("Contas Pagas (Sheets)", f"R$ {contas_pagas:,.2f}")
    c3.metric("Resultado Líquido", f"R$ {fat_total - contas_pagas:,.2f}")
    
    st.divider()
    
    st.dataframe(
        resumo.style.format({
            'Faturamento': 'R$ {:,.2f}',
            '% Share': '{:.1%}',
            'Custo Rateado': 'R$ {:,.2f}',
            'Resultado Líquido': 'R$ {:,.2f}',
            'Margem %': '{:.1%}'
        }), use_container_width=True
    )
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        fig1 = px.bar(resumo, x='Departamento', y='Faturamento', title='Faturamento por Departamento', color='Faturamento', color_continuous_scale='Blues')
        st.plotly_chart(fig1, use_container_width=True)
    with col_g2:
        fig2 = px.pie(resumo, values='Faturamento', names='Departamento', title='Distribuição do Faturamento (% Share)')
        st.plotly_chart(fig2, use_container_width=True)

# 2. COMPARATIVO ENTRE MESES
elif modo_analise == "Comparativo Entre Meses":
    st.subheader("⚔️ Comparativo Direto Entre Dois Meses")
    
    if len(meses_disponiveis) < 2:
        st.warning("É necessário carregar pelo menos 2 meses no histórico para fazer análises comparativas.")
    else:
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            mes1 = st.selectbox("Selecione o Mês Base (Mês 1):", meses_disponiveis, index=0)
        with col_m2:
            mes2 = st.selectbox("Selecione o Mês de Comparação (Mês 2):", meses_disponiveis, index=len(meses_disponiveis)-1)
            
        res1, fat1, cp1 = calcular_resumo(mes1)
        res2, fat2, cp2 = calcular_resumo(mes2)
        
        comp = pd.merge(res1[['Departamento', 'Faturamento', 'Resultado Líquido']], 
                        res2[['Departamento', 'Faturamento', 'Resultado Líquido']], 
                        on='Departamento', how='outer', suffixes=(f' ({mes1})', f' ({mes2})')).fillna(0)
        
        comp['Variação Fat (R$)'] = comp[f'Faturamento ({mes2})'] - comp[f'Faturamento ({mes1})']
        comp['Crescimento (%)'] = (comp['Variação Fat (R$)'] / comp[f'Faturamento ({mes1})']).fillna(0)

        st.divider()
        st.markdown(f"#### 📈 Variação de Faturamento Total: **{((fat2 - fat1)/fat1)*100:+.1f}%**")
        
        st.dataframe(
            comp.style.format({
                f'Faturamento ({mes1})': 'R$ {:,.2f}',
                f'Faturamento ({mes2})': 'R$ {:,.2f}',
                f'Resultado Líquido ({mes1})': 'R$ {:,.2f}',
                f'Resultado Líquido ({mes2})': 'R$ {:,.2f}',
                'Variação Fat (R$)': 'R$ {:,.2f}',
                'Crescimento (%)': '{:+.1%}'
            }), use_container_width=True
        )

        fig_comp = px.bar(
            comp, x='Departamento', y=[f'Faturamento ({mes1})', f'Faturamento ({mes2})'],
            barmode='group', title=f'Comparativo de Faturamento: {mes1} vs {mes2}'
        )
        st.plotly_chart(fig_comp, use_container_width=True)

# 3. VISÃO GERAL DO HISTÓRICO
elif modo_analise == "Visão Geral do Histórico":
    st.subheader("📈 Evolução Histórica Completa")
    
    lista_evo = []
    for m in meses_disponiveis:
        df_m = df_historico[df_historico['Mes_Ano'] == m]
        fat_m = df_m['Líquido'].sum()
        custo_m = obter_contas_mes(m)
        lista_evo.append({
            'Mes_Ano': m,
            'Líquido': fat_m,
            'Contas_Pagas': custo_m,
            'Resultado Líquido': fat_m - custo_m
        })
        
    df_evo = pd.DataFrame(lista_evo)
    
    fig_evo = px.line(
        df_evo, x='Mes_Ano', y=['Líquido', 'Contas_Pagas', 'Resultado Líquido'],
        markers=True, title='Evolução Mensal de Faturamento, Custos e Resultado'
    )
    st.plotly_chart(fig_evo, use_container_width=True)
