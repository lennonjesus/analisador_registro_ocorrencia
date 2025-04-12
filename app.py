import re
import streamlit as st
import PyPDF2
import pandas as pd
from io import BytesIO

def extract_text_from_pdf(pdf_file):
    """
    Extrai o texto de um arquivo PDF.

    Args:
        pdf_file: O arquivo PDF em bytes.

    Returns:
        str: O texto extraído do PDF.
    """
    text = ""
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    for page in pdf_reader.pages:
        text += page.extract_text() or ""  # Extract text, handle None
    return text

def extract_dinamica_fato(text):
    # Encontrar todas as ocorrências de "QUE" que indicam declarações
    partes_texto = text.split('\n')
    inicio_dinamica = False
    final_dinamica = False
    linhas_dinamica = []
    
    for linha in partes_texto:
        # Verificar se chegamos ao início da dinâmica
        if "Dinâmica do Fato" in linha:
            inicio_dinamica = True
            continue
        
        # Verificar se chegamos ao final da dinâmica
        if inicio_dinamica and "QUE MANIFESTA O DESEJO DE REPRESENTAR CRIMINALMENTE" in linha:
            linhas_dinamica.append(linha)
            final_dinamica = True
            break
        
        # Se estamos na seção de dinâmica, adicionar a linha
        if inicio_dinamica and not final_dinamica:
            # Ignorar linhas que parecem ser cabeçalhos/rodapés
            if not any(x in linha for x in ["Data/Impressão:", "Protocolo nº:", "REGISTRO DE OCORRÊNCIA"]):
                linhas_dinamica.append(linha)
    
    return " ".join(linhas_dinamica) if linhas_dinamica else None

def extract_ocorrencia_data_from_text(text):
    """
    Extrai informações padronizadas de um texto de Registro de Ocorrência.

    Args:
        text (str): O texto do Registro de Ocorrência.

    Returns:
        dict: Um dicionário contendo as informações extraídas.
    """
    ocorrencia_data = {}

    # 1. Informações Administrativas
    ocorrencia_data["delegacia"] = re.search(r"(\d+a\.Delegacia de Polícia)", text, re.IGNORECASE)
    ocorrencia_data["numero_registro"] = re.search(r"[Nn][º°\.]?\s*(\d{3}-\d{5}/\d{4})", text)
    ocorrencia_data["data_hora_registro_inicio"] = re.search(r"Data/Hora Início do Registro: (\d{2}/\d{2}/\d{4} \d{2}:\d{2})", text)
    ocorrencia_data["data_hora_registro_final"] = re.search(r"Final do Registro: (\d{2}/\d{2}/\d{4} \d{2}:\d{2})", text)
    ocorrencia_data["origem"] = re.search(r"Origem: (.*?)\.", text)
    ocorrencia_data["circunscricao"] = re.search(r"Circunscrição: (.*)", text)
    ocorrencia_data["responsavel_investigacao"] = re.search(r"Responsável p/ Investigação: (.*)", text)
    ocorrencia_data["despacho_autoridade"] = re.search(r"Despacho da Autoridade\s*(.*?)\s*Envolvido\(s\)", text, re.DOTALL)
    ocorrencia_data["data_procedimento"] = re.search(r"Data do Procedimento: (\d{2}/\d{2}/\d{4} \d{2}:\d{2})", text)
    ocorrencia_data["ultimo_documento_ra"] = re.search(r"Último documento de RA: (.*)", text)
    ocorrencia_data["protocolo_numero"] = re.search(r"Protocolo nº: (.*)", text)

    # 2. Detalhes da Ocorrência
    ocorrencia_data["tipo_ocorrencia"] = re.search(r"Ocorrências\s*(.*)\s*Capitulação", text)
    ocorrencia_data["capitulacao"] = re.search(r"Capitulação: (.*)", text)
    ocorrencia_data["motivo_presumido"] = re.search(r"Motivo Presumido: (.*)", text)
    ocorrencia_data["data_hora_fato"] = re.search(r"Data e Hora do fato: (.*)", text)
    ocorrencia_data["local_fato"] = re.search(r"Local: (.*?)\s*Bairro:", text, re.DOTALL)
    ocorrencia_data["bairro"] = re.search(r"Bairro: (.*?)\s*Municipio:", text)
    ocorrencia_data["municipio"] = re.search(r"Municipio: (.*?)-", text)

    # 3. Envolvidos
    ocorrencia_data["vitima"] = extract_envolvido(text, "Vítima")
    ocorrencia_data["autor"] = extract_envolvido(text, "Autor")

    # 4. Narrativa do Fato
    # ocorrencia_data["dinamica_fato"] = re.search(r"Dinâmica do Fato\s*(.*?)\s*QUE a declarante", text, re.DOTALL)
    ocorrencia_data["dinamica_fato"] = re.search(r"Dinâmica do Fato\s*(.*?)(?:Data/Impressão:|$)", text, re.DOTALL)
    # dinamica = extract_dinamica_fato(text)
    # ocorrencia_data["dinamica_fato"] = dinamica

    # 5. Manifestação da Vítima
    ocorrencia_data["desejo_representar"] = re.search(r"QUE MANIFESTA O DESEJO DE REPRESENTAR CRIMINALMENTE CONTRA OS AUTORES DO FATO\.", text)
    if ocorrencia_data["desejo_representar"]:
        ocorrencia_data["desejo_representar"] = True
    else:
        ocorrencia_data["desejo_representar"] = False

    # Limpeza dos resultados
    for key, value in ocorrencia_data.items():
        if key == "desejo_representar":  # Já tratado anteriormente
            continue
        if key in ["vitima", "autor"]:  # Esses já são dicionários
            continue
        if value and hasattr(value, 'groups') and len(value.groups()) > 0:
            ocorrencia_data[key] = value.group(1).strip()
        else:
            ocorrencia_data[key] = None

    return ocorrencia_data

def extract_envolvido(text, tipo_envolvido):
    """
    Extrai informações sobre a vítima ou autor.
    
    Args:
        text (str): O texto completo do registro.
        tipo_envolvido (str): "Vítima" ou "Autor"
        
    Returns:
        dict: Dicionário com informações do envolvido ou None se não encontrar.
    """
    # Abordagem mais robusta para extrair informações do envolvido
    # Extrair cada campo individualmente
    section_pattern = rf"{tipo_envolvido}(.*?)(?:{('Autor' if tipo_envolvido == 'Vítima' else 'Vítima')}|Dinâmica do Fato)"
    section_match = re.search(section_pattern, text, re.DOTALL | re.IGNORECASE)
    
    if not section_match:
        return None
        
    section_text = section_match.group(1)
    envolvido_data = {}
    
    # Extrair campos individualmente
    fields = {
        "nome": r"Nome: (.*?)(?:\s*-|\n)",
        "cpf": r"CPF/CIC\s+N[°º]\s*(\d{3}\.?\d{3}\.?\d{3}-?\d{2})",
        "endereco": r"Residente na (.*?)(?:\s*Bairro:|\n)",
        "bairro": r"Bairro: (.*?)(?:\s*Municipio:|\n)",
        "municipio": r"Municipio: (.*?)(?:-|\n)",
        "email": r"e-mail: (.*?)(?:\s|$|\n)",
        "pai": r"Filho de: (.*?)(?:\s*e|\n)",
        "mae": r"\s*e\s*(.*?)(?:\s*Data de nascimento:|\n)",
        "data_nascimento": r"Data de nascimento: ([\d/]+)",
        "naturalidade": r"Naturalidade: (.*?)(?:-|\n)",
        "nacionalidade": r"Nacionalidade: (.*?)(?:\s*Sexo:|\n)",
        "sexo": r"Sexo: (.*?)(?:\s*Cor:|\n)",
        "cor": r"Cor: (.*?)(?:\s*Estado Civil:|\n)",
        "estado_civil": r"Estado Civil: (.*?)(?:\s*Ocupação|\n)",
        "ocupacao": r"Ocupação Principal: (.*?)(?:\s|$|\n)"
    }
    
    for field, pattern in fields.items():
        match = re.search(pattern, section_text, re.DOTALL)
        envolvido_data[field] = match.group(1).strip() if match else None
    
    return envolvido_data

# Interface Streamlit
def main():
    st.set_page_config(
        page_title="Extrator de Dados de Registro de Ocorrência",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("Extrator de Dados de Registro de Ocorrência")
    st.write("""
    Esta aplicação extrai informações padronizadas de um arquivo PDF de Registro de Ocorrência.
    Faça o upload do arquivo PDF para visualizar os dados extraídos.
    """)
    
    # Upload do arquivo PDF
    uploaded_file = st.file_uploader("Escolha um arquivo PDF de Registro de Ocorrência", type="pdf")
    
    if uploaded_file is not None:
        st.success("Arquivo carregado com sucesso!")
        
        # Botão para iniciar a extração
        if st.button("Extrair Informações"):
            with st.spinner("Extraindo informações..."):
                # Extrair texto do PDF
                text = extract_text_from_pdf(uploaded_file)
                
                # Opção para visualizar o texto bruto extraído
                with st.expander("Ver texto extraído do PDF"):
                    st.text_area("Texto extraído:", text, height=200)
                
                # Extrair informações do texto
                data = extract_ocorrencia_data_from_text(text)
                
                # Mostrar as informações extraídas
                st.header("Informações Extraídas")
                
                # Dividir a tela em três colunas
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Informações Administrativas")
                    admin_data = {k: v for k, v in data.items() if k not in ["vitima", "autor", "dinamica_fato", "desejo_representar"]}
                    admin_df = pd.DataFrame(list(admin_data.items()), columns=["Campo", "Valor"])
                    st.dataframe(admin_df, use_container_width=True)
                
                with col2:
                    st.subheader("Detalhes da Ocorrência")
                    st.markdown(f"**Dinâmica do Fato:** {data['dinamica_fato'] or 'Não encontrado'}")
                    st.markdown(f"**Desejo de Representar:** {'Sim' if data['desejo_representar'] else 'Não'}")
                
                # Informações da Vítima e Autor
                if data["vitima"]:
                    st.subheader("Dados da Vítima")
                    vitima_df = pd.DataFrame(list(data["vitima"].items()), columns=["Campo", "Valor"])
                    st.dataframe(vitima_df, use_container_width=True)
                else:
                    st.info("Não foram encontrados dados da vítima.")
                
                if data["autor"]:
                    st.subheader("Dados do Autor")
                    autor_df = pd.DataFrame(list(data["autor"].items()), columns=["Campo", "Valor"])
                    st.dataframe(autor_df, use_container_width=True)
                else:
                    st.info("Não foram encontrados dados do autor.")
                
                # Opção para exportar dados
                st.header("Exportar Dados")
                
                # Converter dados para formato exportável
                export_data = {}
                for k, v in data.items():
                    if k not in ["vitima", "autor"]:
                        export_data[k] = v
                
                # Adicionar dados da vítima com prefixo
                if data["vitima"]:
                    for k, v in data["vitima"].items():
                        export_data[f"vitima_{k}"] = v
                
                # Adicionar dados do autor com prefixo
                if data["autor"]:
                    for k, v in data["autor"].items():
                        export_data[f"autor_{k}"] = v
                
                # Opções de exportação
                export_format = st.selectbox(
                    "Selecione o formato de exportação:",
                    ["CSV", "JSON", "Excel"]
                )
                
                if st.button("Exportar Dados"):
                    if export_format == "CSV":
                        # Exportar como CSV
                        df = pd.DataFrame(list(export_data.items()), columns=["Campo", "Valor"])
                        csv = df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="Download CSV",
                            data=csv,
                            file_name=f"ocorrencia_{data.get('numero_registro', 'sem_numero')}.csv",
                            mime="text/csv",
                        )
                    elif export_format == "JSON":
                        # Exportar como JSON
                        json_str = pd.DataFrame([export_data]).to_json(orient="records")
                        st.download_button(
                            label="Download JSON",
                            data=json_str,
                            file_name=f"ocorrencia_{data.get('numero_registro', 'sem_numero')}.json",
                            mime="application/json",
                        )
                    elif export_format == "Excel":
                        # Exportar como Excel
                        df = pd.DataFrame(list(export_data.items()), columns=["Campo", "Valor"])
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            df.to_excel(writer, sheet_name='Dados', index=False)
                        excel_data = output.getvalue()
                        st.download_button(
                            label="Download Excel",
                            data=excel_data,
                            file_name=f"ocorrencia_{data.get('numero_registro', 'sem_numero')}.xlsx",
                            mime="application/vnd.ms-excel",
                        )

if __name__ == "__main__":
    main()