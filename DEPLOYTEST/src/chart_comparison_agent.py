# comparative_chart_agent.py
import openai
import json

class ComparativeChartAgent:
    def __init__(self, openai_api_key, model="gpt-3.5-turbo", temperature=0.0):
        """
        Inicializa el agente para generar datos comparativos.
        :param openai_api_key: API key de OpenAI.
        :param model: Modelo de OpenAI a utilizar.
        :param temperature: Temperatura para la generación.
        """
        self.openai_api_key = openai_api_key
        self.model = model
        self.temperature = temperature
        openai.api_key = self.openai_api_key

    def generate_chart_data(self, comparative_json):
        """
        Envía el JSON estructurado al LLM y obtiene un JSON con 'labels' y 'values'
        para crear un gráfico W
        comparativo.
        
        :param comparative_json: JSON estructurado con las consultas, interpretaciones,
                                 SQL y resultados.
        :return: JSON con las claves 'labels' y 'values'.
        """
        prompt = (
            "Dado el siguiente JSON que contiene las consultas realizadas y sus resultados:\n\n"
            f"{json.dumps(comparative_json, indent=2)}\n\n"
            "Interpreta los datos y genera un conjunto de valores que se puedan utilizar para crear un gráfico comparativo. "
            "Por favor, genera un JSON con las claves \"labels\" y \"values\", donde \"labels\" es una lista de descripciones "
            "y \"values\" es una lista de números correspondientes a cada consulta. Asegúrate de que el formato sea válido JSON."
        )
        
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un experto en análisis de datos y visualización."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
            )
            answer = response["choices"][0]["message"]["content"]
            chart_data = json.loads(answer)
        except Exception as e:
            # En caso de error, se retorna un JSON vacío
            chart_data = {"labels": [], "values": []}
        return chart_data
