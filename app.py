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

# Ligação com Google Sheets via Base64
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
    
    try:
        ws = sh.worksheet('Historico_Vendas')
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title='Historico_Vendas', rows=1000, cols=20)
        ws.append_row([
            'Mes_Ano', 'Data_Hora', 'Departamento', 'Líquido', 'Bruto', 
            'Grupo', 'Tipo_Item', 'Contas_Pagas_Mes'
        ])
    return ws

try:
    ws_historico = ligar_google_sheets()
except Exception as e:
    st.error(f"Erro ao ligar com a base do Google Sheets: {e}")
    st.stop()

# ==========================================
# FUNÇÃO SEGURA PARA LER A PLANILHA
# ==========================================
def carregar_dados_planilha(ws):
    dados_brutos = ws.get_all_values()
    if len(dados_brutos) <= 1:
        return pd.DataFrame(columns=[
            'Mes_Ano', 'Data_Hora', 'Departamento', 'Líquido', 'Bruto', 
            'Grupo', 'Tipo_Item', 'Contas_Pagas_Mes'
        ])
    return pd.DataFrame(dados_brutos[1:], columns=dados_brutos[0])

# ==========================================
# SIDEBAR - CARREGAMENTO / REGISTRO
# ==========================================
st.sidebar.header("📥 Registar Novo Mês no Histórico")

with st.sidebar.expander("Upload de Dados (Simplesvet)"):
    contas_pagas_input = st.number_input("Total Contas Pagas do Mês (R$):", min_value=0.0, value=30000.00, step=500.00)
    uploaded_file = st.file_uploader("Enviar CSV do Simplesvet", type=["csv"])
    
    if uploaded_file and st.button("💾 Guardar/Atualizar no Google Sheets"):
        with st.spinner("A processar e a guardar na base histórica..."):
            df_new = pd.read_csv(uploaded_file, sep=';', encoding='latin1', on_bad_lines='skip')
            
            df_new['Data_Hora'] = pd.to_datetime(df_new['Data e hora'], format='%d/%m/%Y %H:%M', errors='coerce')
            df_new['Mes_Ano'] = df_new['Data_Hora'].dt.strftime('%m/%Y')
            
            for col in ['Líquido', 'Bruto']:
                if col in df_new.columns:
                    df_new[col] = (
                        df_new[col].astype(str)
                        .str.replace('.', '', regex=False)
                        .str.replace(',', '.', regex=False)
                        .astype(float)
                    )

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
                'Líquido': df_new['Líquido'],
                'Bruto': df_new['Bruto'],
                'Grupo': df_new['Grupo'].fillna('N/A'),
                'Tipo_Item': df_new['Tipo do Item'].fillna('N/A'),
                'Contas_Pagas_Mes': contas_pagas_input
            }).dropna(subset=['Mes_Ano'])

            df_existente = carregar_dados_planilha(ws_historico)
            
            mes_carregado = df_salvar['Mes_Ano'].iloc[0]
            
            if not df_existente.empty and 'Mes_Ano' in df_existente.columns:
                df_existente = df_existente[df_existente['Mes_Ano'] != mes_carregado]
                df_final_base = pd.concat([df_existente, df_salvar], ignore_index=True)
            else:
                df_final_base = df_salvar

            ws_historico.clear()
            ws_historico.update([df_final_base.columns.values.tolist()] + df_final_base.values.tolist())
            st.success(f"Mês {mes_carregado} registado/atualizado com sucesso!")
            st.rerun()

# ==========================================
# CARREGAMENTO DA BASE HISTÓRICA DO GOOGLE SHEETS
# ==========================================
df_historico = carregar_dados_planilha(ws_historico)

if df_historico.empty:
    st.info("ℹ️ A base de dados no Google Sheets está vazia. Use o painel lateral para enviar o primeiro CSV do Simplesvet.")
    st.stop()

df_historico['Líquido'] = pd.to_numeric(df_historico['Líquido'], errors='coerce').fillna(0)
df_historico['Contas_Pagas_Mes'] = pd.to_numeric(df_historico['Contas_Pagas_Mes'], errors='coerce').fillna(0)
meses_disponiveis = sorted(df_historico['Mes_Ano'].unique().tolist())

# ==========================================
# NAVEGAÇÃO E ANÁLISE NO STREAMLIT
# ==========================================
st.sidebar.divider()
modo_analise = st.sidebar.radio("🔍 Modo de Análise", ["Mês Individual", "Comparativo Entre Meses", "Visão Geral do Histórico"])

def calcular_resumo(df_filtrado):
    contas_pagas = df_filtrado['Contas_Pagas_Mes'].iloc[0] if not df_filtrado.empty else 0
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
    
    df_mes = df_historico[df_historico['Mes_Ano'] == mes_sel]
    resumo, fat_total, contas_pagas = calcular_resumo(df_mes)
    
    st.subheader(f"📊 Relatório Financeiro: {mes_sel}")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Faturamento Total", f"R$ {fat_total:,.2f}")
    c2.metric("Contas Pagas", f"R$ {contas_pagas:,.2f}")
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
            
        res1, fat1, cp1 = calcular_resumo(df_historico[df_historico['Mes_Ano'] == mes1])
        res2, fat2, cp2 = calcular_resumo(df_historico[df_historico['Mes_Ano'] == mes2])
        
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
    
    df_evo = df_historico.groupby('Mes_Ano').agg({
        'Líquido': 'sum',
        'Contas_Pagas_Mes': 'first'
    }).reset_index()
    
    df_evo['Resultado Líquido'] = df_evo['Líquido'] - df_evo['Contas_Pagas_Mes']
    
    fig_evo = px.line(
        df_evo, x='Mes_Ano', y=['Líquido', 'Contas_Pagas_Mes', 'Resultado Líquido'],
        markers=True, title='Evolução Mensal de Faturamento, Custos e Resultado'
    )
    st.plotly_chart(fig_evo, use_container_width=True)
