#chart_handl

def get_chart_type_name(chart_type):
   
    chart_names = {
        "bar": "gráfico de barras",
        "line": "gráfico de líneas",
        "area": "gráfico de área"
    }
    return chart_names.get(chart_type, chart_type)


def check_if_chart_request(query):
  
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
    return False, None
