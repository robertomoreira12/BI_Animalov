import json
import gspread
import pandas as pd
import streamlit as st

# Configuração da Página no Navegador
st.set_page_config(page_title="Animalov - Atualizador de BI", page_icon="🐾", layout="centered")

st.title("🐾 Animalov - Atualizador Automático do BI")
st.markdown("Faça o upload do extrato de vendas do Simplesvet e atualize o painel no Google Sheets em 1 clique.")

# 1. Entrada do Valor de Contas Pagas do Mês
contas_pagas = st.number_input(
    "Informe o Total de Contas Pagas no Mês (R$):", 
    min_value=0.0, 
    value=30000.00, 
    step=100.00,
    format="%.2f"
)

# 2. Upload do Arquivo CSV do Simplesvet
uploaded_file = st.file_uploader("Arraste ou selecione o arquivo CSV do Simplesvet", type=["csv"])

if uploaded_file is not None:
    if st.button("🚀 Processar e Atualizar Google Sheets", type="primary"):
        with st.spinner("Processando dados e enviando para o Google Sheets..."):
            try:
                # Lê o CSV enviado pelo navegador
                df = pd.read_csv(uploaded_file, sep=';', encoding='latin1', on_bad_lines='skip')
                
                # Tratamento de Datas
                df['Data_Hora'] = pd.to_datetime(df['Data e hora'], format='%d/%m/%Y %H:%M', errors='coerce')
                df['Data_Apenas'] = df['Data_Hora'].dt.date
                df['Mes_Ano'] = df['Data_Hora'].dt.strftime('%m/%Y')
                
                # Tratamento de Valores Numéricos
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
                    tipo = str(row.get('Tipo do Item', ''))
                    
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

                resumo = df.groupby('Departamento')['Líquido'].agg(
                    Faturamento='sum'
                ).reset_index()

                resumo['% Share'] = (resumo['Faturamento'] / faturamento_total)
                resumo['Rateio Custo Total (R$)'] = resumo['% Share'] * contas_pagas
                resumo['Custo Diário (R$)'] = resumo['Rateio Custo Total (R$)'] / dias_trabalhados
                resumo['Resultado Líquido (R$)'] = resumo['Faturamento'] - resumo['Rateio Custo Total (R$)']
                resumo['Margem (%)'] = resumo['Resultado Líquido (R$)'] / resumo['Faturamento']

                resumo = resumo.sort_values(by='Faturamento', ascending=False).reset_index(drop=True)

                # Conexão Segura com o Google Sheets via Streamlit Secrets
                # (As credenciais ficam salvas de forma segura no painel do Streamlit Cloud)
                credenciais_dict = dict(st.secrets["gcp_service_account"])
                gc = gspread.service_account_from_dict(credenciais_dict)
                
                id_planilha = "13gngB_axx-1L__qqoA2PGUXFp9XVexJA_zYQADUNOtQ"
                sh = gc.open_by_key(id_planilha)
                
                try:
                    ws = sh.worksheet('Dashboard')
                except gspread.exceptions.WorksheetNotFound:
                    ws = sh.add_worksheet(title='Dashboard', rows=100, cols=20)

                ws.clear()

                mes_ref = df['Mes_Ano'].iloc[0] if not df.empty else 'N/A'
                cabecalho_kpis = [
                    ["Mês/Ano", mes_ref],
                    ["Dias Úteis Trabalhados", dias_trabalhados],
                    ["Total de Contas Pagas (R$)", contas_pagas],
                    []
                ]
                
                tabela_headers = [
                    "Departamento", "Faturamento (R$)", "% Share", 
                    "Rateio Custo Total (R$)", "Custo Diário (R$)", 
                    "Resultado Líquido (R$)", "Margem (%)"
                ]
                
                tabela_linhas = resumo.values.tolist()
                
                linha_total = [
                    "TOTAL",
                    faturamento_total,
                    1.0,
                    contas_pagas,
                    contas_pagas / dias_trabalhados if dias_trabalhados > 0 else 0,
                    faturamento_total - contas_pagas,
                    (faturamento_total - contas_pagas) / faturamento_total
                ]
                
                dados_finais = cabecalho_kpis + [tabela_headers] + tabela_linhas + [linha_total]
                ws.update('A1', dados_finais)
                
                st.success("✅ Dashboard atualizado com sucesso no Google Sheets!")
                
                # Exibe uma prévia na tela
                st.subheader("Prévia do Resultado Processado:")
                st.dataframe(resumo, use_container_width=True)

            except Exception as e:
                st.error(f"Ocorreu um erro ao processar: {e}")