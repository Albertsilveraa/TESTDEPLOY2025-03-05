# modules/data_analyzer.py

import pandas as pd
import matplotlib.pyplot as plt

class DataAnalysisAgent:
    """
    Agente encargado de convertir timestamps en formato unixtime a formato datetime
    y de realizar análisis estadístico sobre los datos para generar gráficos comparativos.
    """

    def __init__(self, time_unit='s'):
        """
        :param time_unit: Unidad de los timestamps epoch ('s' para segundos, 'ms' para milisegundos, etc.).
        """
        self.time_unit = time_unit

    def convert_epoch_to_datetime(self, df, time_column):
        """
        Convierte una columna con valores epoch a formato datetime.
        
        :param df: DataFrame que contiene la columna de tiempos en epoch.
        :param time_column: Nombre de la columna con los timestamps.
        :return: DataFrame con la columna convertida a datetime.
        """
        df[time_column] = pd.to_datetime(df[time_column], unit=self.time_unit)
        return df

    def aggregate_by_time(self, df, time_column, value_column, freq='D'):
        """
        Agrupa los datos por una frecuencia de tiempo especificada y calcula estadísticas
        (por ejemplo, media, suma y conteo).
        
        :param df: DataFrame con los datos.
        :param time_column: Nombre de la columna con el timestamp (se convertirá a datetime si es necesario).
        :param value_column: Nombre de la columna numérica a analizar.
        :param freq: Frecuencia de agrupación ('D' para diario, 'M' para mensual, etc.).
        :return: DataFrame con las estadísticas agrupadas.
        """
        df = df.copy()
        # Asegurarse de que la columna de tiempo esté en formato datetime
        if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
            df[time_column] = pd.to_datetime(df[time_column], unit=self.time_unit)
        # Establecer el índice temporal para el reagrupamiento
        df.set_index(time_column, inplace=True)
        agg_df = df[value_column].resample(freq).agg(['mean', 'sum', 'count'])
        agg_df.reset_index(inplace=True)
        return agg_df

    def plot_aggregated_data(self, agg_df, time_column, value_columns, title="Análisis Comparativo", ylabel="Valores"):
        """
        Genera un gráfico comparativo a partir de los datos agrupados.
        
        :param agg_df: DataFrame con los datos agrupados.
        :param time_column: Nombre de la columna que contiene la fecha/hora.
        :param value_columns: Lista de nombres de columnas que se desean graficar.
        :param title: Título del gráfico.
        :param ylabel: Etiqueta para el eje Y.
        :return: Objeto figura de matplotlib.
        """
        fig, ax = plt.subplots(figsize=(10, 6))
        for col in value_columns:
            ax.plot(agg_df[time_column], agg_df[col], marker='o', label=col)
        ax.set_title(title)
        ax.set_xlabel("Fecha")
        ax.set_ylabel(ylabel)
        ax.legend()
        ax.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()
        return fig
