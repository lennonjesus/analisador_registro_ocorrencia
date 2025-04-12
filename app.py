import re
import PyPDF2

def extract_ocorrencia_data_from_pdf(pdf_path):
    """
    Extrai informações padronizadas de um arquivo PDF de Registro de Ocorrência.

    Args:
        pdf_path (str): O caminho para o arquivo PDF.

    Returns:
        dict: Um dicionário contendo as informações extraídas.
    """
    text = extract_text_from_pdf(pdf_path)
    return extract_ocorrencia_data_from_text(text)

def extract_text_from_pdf(pdf_path):
    """
    Extrai o texto de um arquivo PDF.

    Args:
        pdf_path (str): O caminho para o arquivo PDF.

    Returns:
        str: O texto extraído do PDF.
    """
    text = ""
    with open(pdf_path, "rb") as pdf_file:
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            text += page.extract_text() or ""  # Extract text, handle None
    return text

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
    ocorrencia_data["numero_registro"] = re.search(r"Nº\s+(\d{3}-\d{5}/\d{4})", text)
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
    ocorrencia_data["dinamica_fato"] = re.search(r"Dinâmica do Fato\s*(.*?)\s*QUE a declarante", text, re.DOTALL)

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
        "cpf": r"CPF/CIC N° ([\d\.\-]+)",
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

# Exemplo de uso
if __name__ == "__main__":
    pdf_path = "documentos/registro_ocorrencia.pdf"  # Substitua pelo caminho do seu arquivo PDF
    data = extract_ocorrencia_data_from_pdf(pdf_path)
    
    # Imprime cada dado em uma linha separada
    print("\n===== DADOS DA OCORRÊNCIA =====")
    for key, value in data.items():
        if key not in ["vitima", "autor"]:  # Trataremos esses separadamente
            print(f"{key}: {value}")
    
    # Imprime dados da vítima, se houver
    if data["vitima"]:
        print("\n===== DADOS DA VÍTIMA =====")
        for key, value in data["vitima"].items():
            print(f"vitima_{key}: {value}")
    
    # Imprime dados do autor, se houver
    if data["autor"]:
        print("\n===== DADOS DO AUTOR =====")
        for key, value in data["autor"].items():
            print(f"autor_{key}: {value}")