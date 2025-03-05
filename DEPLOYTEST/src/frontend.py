import streamlit as st
import pandas as pd
import time
from app import process_query  # Importamos la función del backend
from data_analyzer import DataAnalysisAgent
import matplotlib.pyplot as plt
import seaborn as sns


#frontend
# Configuración de la página
st.set_page_config(
    page_title="ChatBot SQL",
    page_icon="🤖",
    layout="wide"
)

# Estilos personalizados para que parezca un chatbot
st.markdown("""
    <style>
        .stChatMessage {
            padding: 10px;
            border-radius: 10px;
            margin-bottom: 5px;
            max-width: 80%;
            word-wrap: break-word;
        }
        .stChatMessageUser {
            background-color: #0084ff;
            color: white;
            align-self: flex-end;
            text-align: right;
        }
        .stChatMessageAssistant {
            background-color: #f1f0f0;
            color: black;
            align-self: flex-start;
            text-align: left;
        }
        .stChatInput {
            border-radius: 20px;
            padding: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# Función para generar gráficos según el tipo solicitado
def generate_chart(df, chart_type="bar", x_column=None, y_column=None, title=""):
    """
    Genera un gráfico según el tipo solicitado
    
    :param df: DataFrame con los datos
    :param chart_type: Tipo de gráfico (bar, line, area)
    :param x_column: Columna para el eje X
    :param y_column: Columna para el eje Y
    :param title: Título del gráfico
    :return: None (el gráfico se muestra directamente en Streamlit)
    """
    if df.empty:
        st.warning("No hay datos suficientes para generar el gráfico")
        return
    
    # Si no se especifican columnas, intentamos inferirlas
    if x_column is None:
        # Buscar columnas de fecha/tiempo o usar la primera columna
        datetime_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
        x_column = datetime_cols[0] if datetime_cols else df.columns[0]
    
    if y_column is None:
        # Usar la primera columna numérica que no sea la columna X
        numeric_cols = [col for col in df.columns if df[col].dtype in ['int64', 'float64'] and col != x_column]
        y_column = numeric_cols[0] if numeric_cols else df.columns[1] if len(df.columns) > 1 else None
    
    if y_column is None:
        st.warning("No se pudo determinar una columna numérica para el eje Y")
        return
    
    # Generar el gráfico según el tipo
    fig, ax = plt.subplots(figsize=(10, 6))
    
    if chart_type == "bar":
        st.subheader("📊 Gráfico de Barras")
        st.bar_chart(df.set_index(x_column)[y_column])
    
    elif chart_type == "line":
        st.subheader("📈 Gráfico de Líneas")
        st.line_chart(df.set_index(x_column)[y_column])
    
    elif chart_type == "area":
        st.subheader("📉 Gráfico de Área")
        st.area_chart(df.set_index(x_column)[y_column])
    
    else:
        st.warning(f"Tipo de gráfico '{chart_type}' no soportado")

# Función para detectar si el usuario está solicitando un gráfico
def is_chart_request(query):
    """
    Detecta si la consulta del usuario está solicitando un gráfico
    
    :param query: Consulta del usuario
    :return: (bool, str) - Indica si es una solicitud de gráfico y el tipo
    """
    query_lower = query.lower()
    
    chart_keywords = {
        "gráfico de barras": "bar",
        "grafico de barras": "bar", 
        "gráfica de barras": "bar",
        "grafica de barras": "bar",
        "muestra en barras": "bar",
        "graficar en barras": "bar",
        "visualizar en barras": "bar",
        
        "gráfico de líneas": "line",
        "grafico de lineas": "line",
        "gráfica de líneas": "line",
        "grafica de lineas": "line",
        "muestra en líneas": "line",
        "muestra en lineas": "line",
        "graficar en líneas": "line",
        "graficar en lineas": "line",
        "visualizar en líneas": "line",
        "visualizar en lineas": "line",
        
        "gráfico de área": "area",
        "grafico de area": "area",
        "gráfica de área": "area",
        "grafica de area": "area",
        "muestra en área": "area",
        "muestra en area": "area",
        "graficar en área": "area",
        "graficar en area": "area",
        "visualizar en área": "area",
        "visualizar en area": "area"
    }
    
    for keyword, chart_type in chart_keywords.items():
        if keyword in query_lower:
            return True, chart_type
    
    # Verificar palabras sueltas si no se encontró una frase completa
    if any(word in query_lower for word in ["gráfico", "grafico", "gráfica", "grafica", "graficar", "visualizar"]):
        # Determinar el tipo de gráfico por defecto
        if "barra" in query_lower:
            return True, "bar"
        elif any(word in query_lower for word in ["línea", "linea", "líneas", "lineas"]):
            return True, "line"
        elif any(word in query_lower for word in ["área", "area"]):
            return True, "area"
        else:
            # Si solo pide un gráfico sin especificar tipo, usamos barras por defecto
            return True, "bar"
    
    return False, None

# Sidebar: Configuración de la base de datos
with st.sidebar:
    st.header("⚙️ Configuración de la Base de Datos")
    openai_api_key = st.text_input("OpenAI API Key", type="password", key="openai_api_key")
    db_name = st.text_input("Nombre de la Base de Datos", key="db_name")
    db_user = st.text_input("Usuario", key="db_user")
    db_password = st.text_input("Contraseña", type="password", key="db_password")
    db_host = st.text_input("Host", value="localhost", key="db_host")
    db_port = st.text_input("Puerto", value="3306", key="db_port")

    if st.button("Actualizar Credenciales"):
        st.success("✅ Credenciales actualizadas.")

# Guardar credenciales en un diccionario
db_config = {
    "database": db_name,
    "user": db_user,
    "password": db_password,
    "host": db_host,
    "port": int(db_port) if db_port.isdigit() else 3306
}

# **Historial de conversación**
if "messages" not in st.session_state:
    st.session_state.messages = []

# **Mostrar el historial de conversación**
st.title("🤖 ChatBot SQL - Asistente de Base de Datos")

for message in st.session_state.messages:
    role = message["role"]
    content = message["content"]

    with st.chat_message(role):
        if isinstance(content, dict):
            if "message" in content:
                st.markdown(content["message"])
            if "sql_query" in content:
                st.markdown("📝 **Consulta SQL generada:**")
                st.code(content["sql_query"], language="sql")
            if "data" in content and content["data"]:
                df = pd.DataFrame(content["data"], columns=content.get("columns", []))
                st.dataframe(df)
                
                # Si hay una solicitud de gráfico, mostrarlo
                if content.get("chart_type"):
                    if content["chart_type"] == "bar":
                        st.bar_chart(df)
                    elif content["chart_type"] == "line":
                        st.line_chart(df)
                    elif content["chart_type"] == "area":
                        st.area_chart(df)
                    
            if "analysis" in content:
                st.markdown("📊 **Análisis Estadístico**")
                agg_data = content["analysis"]
                agg_df = pd.DataFrame(agg_data)
                st.dataframe(agg_df)
                
                # Generar gráfico automáticamente para los datos de análisis
                if "timestamp" in agg_df.columns:
                    st.line_chart(agg_df.set_index("timestamp"))
        else:
            st.markdown(content)

# **Entrada de usuario tipo chat**
user_input = st.chat_input("Escribe tu consulta...")

if user_input:
    # Verificar si es una solicitud de gráfico
    is_chart, chart_type = is_chart_request(user_input)
    
    # Mostrar el mensaje del usuario en el chat
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # **Verificar credenciales antes de continuar**
    required_fields = [openai_api_key, db_name, db_user, db_host, db_port]
    
    if not all(required_fields):
        st.error("⚠️ Completa todas las credenciales en la barra lateral.")
    else:
        with st.spinner("⏳ Procesando tu consulta..."):
            result = process_query(user_input, db_config, openai_api_key)

        # Construir la respuesta del asistente
        assistant_response = {
            "sql_query": result["sql"],
            "data": result["resultados"]["data"] if isinstance(result["resultados"], dict) and "data" in result["resultados"] else 
                   [r.get("data", []) for r in result["resultados"]] if isinstance(result["resultados"], list) else [],
            "columns": result["resultados"]["columns"] if isinstance(result["resultados"], dict) and "columns" in result["resultados"] else 
                      [r.get("columns", []) for r in result["resultados"]] if isinstance(result["resultados"], list) else [],
            "message": result["formatted_response"]
        }
        
        # Si es una solicitud de gráfico, agregar el tipo
        if is_chart:
            assistant_response["chart_type"] = chart_type
        
        if result.get("analysis_result"):
            assistant_response["analysis"] = result["analysis_result"]["agg_data"]

        # Mostrar el mensaje del asistente en el chat
        st.session_state.messages.append({"role": "assistant", "content": assistant_response})
        with st.chat_message("assistant"):
            st.markdown(result["formatted_response"])

            if isinstance(assistant_response["sql_query"], list):
                st.markdown("📝 **Consultas SQL generadas:**")
                for idx, sql in enumerate(assistant_response["sql_query"], 1):
                    st.markdown(f"**Consulta {idx}:**")
                    st.code(sql, language="sql")
            else:
                st.markdown("📝 **Consulta SQL generada:**")
                st.code(assistant_response["sql_query"], language="sql")

            # Determinar si tenemos múltiples consultas con resultados
            has_multiple_results = isinstance(assistant_response["data"], list) and all(isinstance(i, list) for i in assistant_response["data"])
            
            if has_multiple_results:
                for idx, (data, columns) in enumerate(zip(assistant_response["data"], assistant_response["columns"])):
                    if data:  # Solo mostrar si hay datos
                        st.markdown(f"### 📊 Resultado {idx + 1}")
                        df = pd.DataFrame(data, columns=columns)
                        st.dataframe(df)
                        
                        # Generar gráfico si se solicitó
                        if is_chart:
                            if chart_type == "bar":
                                st.bar_chart(df)
                            elif chart_type == "line":
                                st.line_chart(df)
                            elif chart_type == "area":
                                st.area_chart(df)
            else:
                if assistant_response.get("data"):
                    df = pd.DataFrame(assistant_response["data"], columns=assistant_response.get("columns", []))
                    st.dataframe(df)
                    
                    # Generar gráfico si se solicitó
                    if is_chart:
                        if chart_type == "bar":
                            st.bar_chart(df)
                        elif chart_type == "line":
                            st.line_chart(df)
                        elif chart_type == "area":
                            st.area_chart(df)

            if assistant_response.get("analysis"):
                st.markdown("📊 **Análisis Estadístico**")
                agg_df = pd.DataFrame(assistant_response["analysis"])
                st.dataframe(agg_df)
                
                # Generar gráfico automáticamente para los datos de análisis
                if len(agg_df.columns) >= 2:  # Al menos necesitamos dos columnas para un gráfico
                    if is_chart:
                        if chart_type == "bar":
                            st.bar_chart(agg_df)
                        elif chart_type == "line":
                            st.line_chart(agg_df)
                        elif chart_type == "area":
                            st.area_chart(agg_df)
                    else:
                        # Por defecto mostrar gráfico de líneas para análisis temporal
                        st.line_chart(agg_df)