import streamlit as st
import pandas as pd
import plotly.express as px

# Configuração da Página no Navegador (Layout Largo para aproveitar a tela)
st.set_page_config(page_title="Animalov - BI & Gestão", page_icon="🐾", layout="wide")

st.title("🐾 Animalov - Dashboard de Inteligência de Negócios (BI)")
st.markdown("Acompanhe o faturamento, rateio de custos e margem líquida por departamento em tempo real.")

# Barra lateral para configurações e filtros
st.sidebar.header("⚙️ Parâmetros do Mês")
contas_pagas = st.sidebar.number_input(
    "Informe o Total de Contas Pagas (R$):", 
    min_value=0.0, 
    value=30000.00, 
    step=100.00,
    format="%.2f"
)

# Upload do arquivo CSV do Simplesvet
uploaded_file = st.sidebar.file_uploader("📂 Envie o CSV do Simplesvet", type=["csv"])

if uploaded_file is not None:
    # Processamento dos dados
    df = pd.read_csv(uploaded_file, sep=';', encoding='latin1', on_bad_lines='skip')
    
    df['Data_Hora'] = pd.to_datetime(df['Data e hora'], format='%d/%m/%Y %H:%M', errors='coerce')
    df['Data_Apenas'] = df['Data_Hora'].dt.date
    df['Mes_Ano'] = df['Data_Hora'].dt.strftime('%m/%Y')
    
    colunas_valores = ['Líquido', 'Bruto', 'Valor Unitário']
    for col in colunas_valores:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace('.', '', regex=False)
                .str.replace(',', '.', regex=False)
                .astype(float)
            )

    # Classificação de Departamentos
    def classificar_departamento(row):
        grupo = str(row.get('Grupo', ''))
        tipo = str(row.get('Tipo du Item', ''))
        
        if grupo == 'Farmácia':
            return 'Farmácia (Medicamentos)'
        if tipo == 'Produto':
            return 'Petshop (Produtos)'
        if grupo in ['Banho', 'Tosa', 'Hidratação', 'Desembolo', 'Corte de Unhas', 'Higiene e Beleza']:
            return 'Estética Pet'
        if grupo in ['Consultas', 'Vacinas', 'Cirurgias', 'Exames', 'Procedimentos'] or tipo == 'Procedimento Petlove':
            return 'Clínica Veterinária'
        if grupo == 'Transporte':
            return 'Táxi Pet'
        if grupo == 'Hospedagem':
            return 'Creche & Hotel'
        return 'Outros'

    df['Departamento'] = df.apply(classificar_departamento, axis=1)

    faturamento_total = df['Líquido'].sum()
    dias_trabalhados = df['Data_Apenas'].nunique()
    mes_ref = df['Mes_Ano'].iloc[0] if not df.empty else 'N/A'

    resumo = df.groupby('Departamento')['Líquido'].agg(
        Faturamento='sum'
    ).reset_index()

    resumo['% Share'] = (resumo['Faturamento'] / faturamento_total)
    resumo['Rateio Custo Total (R$)'] = resumo['% Share'] * contas_pagas
    resumo['Custo Diário (R$)'] = resumo['Rateio Custo Total (R$)'] / (dias_trabalhados if dias_trabalhados > 0 else 1)
    resumo['Resultado Líquido (R$)'] = resumo['Faturamento'] - resumo['Rateio Custo Total (R$)']
    resumo['Margem (%)'] = resumo['Resultado Líquido (R$)'] / resumo['Faturamento']

    resumo = resumo.sort_values(by='Faturamento', ascending=False).reset_index(drop=True)

    # ==========================================
    # EXIBIÇÃO DO BI NA INTERFACE DO STREAMLIT
    # ==========================================

    st.markdown(f"### 📊 Visão Geral do Mês: **{mes_ref}**")
    
    # Cards de KPIs no topo
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Faturamento Total", f"R$ {faturamento_total:,.2f}")
    col2.metric("📋 Total Contas Pagas", f"R$ {contas_pagas:,.2f}")
    col3.metric("🎯 Resultado Líquido", f"R$ {faturamento_total - contas_pagas:,.2f}")
    col4.metric("📅 Dias Úteis", dias_trabalhados)

    st.divider()

    # Tabela de Indicadores Formatada
    st.subheader("📋 Demonstrativo Financeiro por Departamento")
    st.dataframe(
        resumo.style.format({
            'Faturamento': 'R$ {:,.2f}',
            '% Share': '{:.1%}',
            'Rateio Custo Total (R$)': 'R$ {:,.2f}',
            'Custo Diário (R$)': 'R$ {:,.2f}',
            'Resultado Líquido (R$)': 'R$ {:,.2f}',
            'Margem (%)': '{:.1%}'
        }),
        use_container_width=True
    )

    st.divider()

   # Gráficos Interativos
    st.subheader("📈 Análise Gráfica")
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        fig_fat = px.bar(
            resumo, 
            x='Departamento', 
            y='Faturamento', 
            title='Faturamento por Departamento',
            text_auto='.2s',
            color='Faturamento',
            color_continuous_scale='Blues'
        )
        st.plotly_chart(fig_fat, use_container_width=True)

    with col_g2:
        fig_res = px.bar(
            resumo, 
            x='Departamento', 
            y='Resultado Líquido (R$)', 
            title='Resultado Líquido por Departamento',
            text_auto='.2s',
            color='Resultado Líquido (R$)',
            color_continuous_scale='Greens'
        )
        st.plotly_chart(fig_res, use_container_width=True)

else:
    st.info("👈 Por favor, defina o valor das contas pagas na barra lateral e faça o upload do arquivo CSV do Simplesvet para gerar o seu BI.")
