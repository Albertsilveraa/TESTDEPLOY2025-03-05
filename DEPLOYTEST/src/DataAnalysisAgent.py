import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt

class DataAnalysisAgent:
    """
    Agente encargado de realizar análisis estadísticos y preparar datos para visualización.
    """
    
    def __init__(self, time_unit='ms'):
        """
        Inicializa el agente de análisis de datos.
        
        :param time_unit: Unidad de tiempo en la que están los timestamps ('ms' para milisegundos, 's' para segundos)
        """
        self.time_unit = time_unit
    
    def convert_epoch_to_datetime(self, df, timestamp_col):
        """
        Convierte una columna de timestamp epoch a formato datetime.
        
        :param df: DataFrame que contiene la columna de timestamp
        :param timestamp_col: Nombre de la columna que contiene los timestamps
        :return: DataFrame con la columna convertida
        """
        if timestamp_col in df.columns:
            if self.time_unit == 'ms':
                df[timestamp_col] = pd.to_datetime(df[timestamp_col], unit='ms')
            else:
                df[timestamp_col] = pd.to_datetime(df[timestamp_col], unit='s')
        return df
    
    def aggregate_by_time(self, df, timestamp_col, value_col, freq='D'):
        """
        Agrega datos por una frecuencia de tiempo especificada.
        
        :param df: DataFrame con los datos
        :param timestamp_col: Columna de timestamp
        :param value_col: Columna de valores a agregar
        :param freq: Frecuencia de tiempo ('D' para día, 'H' para hora, etc.)
        :return: DataFrame agregado
        """
        if timestamp_col not in df.columns or value_col not in df.columns:
            return pd.DataFrame()
        
        # Asegurarse de que la columna timestamp es datetime
        if not pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
            df = self.convert_epoch_to_datetime(df, timestamp_col)
        
        # Agrupar por tiempo y calcular estadísticas
        grouped = df.groupby(pd.Grouper(key=timestamp_col, freq=freq)).agg({
            value_col: ['count', 'sum', 'mean', 'min', 'max']
        })
        
        # Aplanar los nombres de columnas
        grouped.columns = [f"{value_col}_{stat}" for _, stat in grouped.columns]
        
        # Reiniciar el índice para que timestamp sea una columna
        grouped = grouped.reset_index()
        
        return grouped
    
    def prepare_for_chart(self, df, x_col, y_col, chart_type='line'):
        """
        Prepara los datos para un gráfico específico.
        
        :param df: DataFrame con los datos
        :param x_col: Columna para el eje X
        :param y_col: Columna para el eje Y
        :param chart_type: Tipo de gráfico ('line', 'bar', 'area')
        :return: DataFrame preparado para el gráfico
        """
        if x_col not in df.columns or y_col not in df.columns:
            return pd.DataFrame()
        
        # Para gráficos de líneas y áreas, asegurarse de que los datos están ordenados
        if chart_type in ['line', 'area']:
            df = df.sort_values(by=x_col)
        
        # Para gráficos de barras, si hay muchos datos, podemos agrupar o limitar
        if chart_type == 'bar' and len(df) > 30:
            # Limitar a los primeros 30 registros como ejemplo
            # Otra opción sería agrupar los datos 
            df = df.head(30)
        
        return df

    def analyze_time_series(self, df, timestamp_col, value_col):
        """
        Realiza un análisis completo de series temporales.
        
        :param df: DataFrame con los datos
        :param timestamp_col: Columna de timestamp
        :param value_col: Columna de valores a analizar
        :return: Dict con los resultados del análisis
        """
        if timestamp_col not in df.columns or value_col not in df.columns:
            return {}
        
        # Convertir a datetime si es necesario
        if not pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
            df = self.convert_epoch_to_datetime(df, timestamp_col)
        
        # Ordenar por tiempo
        df = df.sort_values(by=timestamp_col)
        
        # Calcular estadísticas básicas
        stats = {
            'count': int(df[value_col].count()),
            'mean': float(df[value_col].mean()),
            'std': float(df[value_col].std()),
            'min': float(df[value_col].min()),
            'max': float(df[value_col].max()),
            'first_date': df[timestamp_col].min().strftime('%Y-%m-%d'),
            'last_date': df[timestamp_col].max().strftime('%Y-%m-%d')
        }
        
        # Agregaciones diarias, semanales y mensuales
        daily = self.aggregate_by_time(df, timestamp_col, value_col, freq='D')
        weekly = self.aggregate_by_time(df, timestamp_col, value_col, freq='W')
        monthly = self.aggregate_by_time(df, timestamp_col, value_col, freq='M')
        
        # Convertir a formato de diccionario para JSON
        result = {
            'stats': stats,
            'daily': {
                'timestamp': daily[timestamp_col].dt.strftime('%Y-%m-%d').tolist(),
                'count': daily[f"{value_col}_count"].tolist(),
                'mean': daily[f"{value_col}_mean"].tolist()
            },
            'weekly': {
                'timestamp': weekly[timestamp_col].dt.strftime('%Y-%m-%d').tolist(),
                'count': weekly[f"{value_col}_count"].tolist(),
                'mean': weekly[f"{value_col}_mean"].tolist()
            },
            'monthly': {
                'timestamp': monthly[timestamp_col].dt.strftime('%Y-%m-%d').tolist(),
                'count': monthly[f"{value_col}_count"].tolist(),
                'mean': monthly[f"{value_col}_mean"].tolist()
            }
        }
        
        return result