import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Tablero Real PTL por Brazos", layout="wide", page_icon="⚖️")

# --- FUNCIONES DE LECTURA Y NORMALIZACIÓN (AL INICIO) ---
def leer_archivo(archivo):
    """Detecta si es CSV o Excel y lo lee con el formato correcto."""
    if archivo.name.endswith('.csv'):
        try: 
            return pd.read_csv(archivo, encoding='utf-8')
        except UnicodeDecodeError: 
            return pd.read_csv(archivo, encoding='latin1', sep=None, engine='python')
    else: 
        return pd.read_excel(archivo)

def limpiar_sku(series):
    return series.astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

def limpiar_posicion(series):
    return series.astype(str).str.strip().str.upper().str.replace(r'\.0$', '', regex=True)

# --- CLASIFICADOR OPERATIVO ESTRICTO (TU LAYOUT) ---
def clasificar_linea_y_brazo(estacion, area_text):
    est = str(estacion).strip().upper()
    txt = str(area_text).upper()
    
    # Filtro LIT Aparte
    if est.startswith('LIT'):
        if 'LINEA 1' in txt or 'LINEA1' in txt:
            return 1, 'LIT', 'Revistas LIT'
        else:
            return 2, 'LIT', 'Revistas LIT'
            
    # LINEA 1
    if est == 'M01':
        return 1, 'MUSEO', 'Museo M01'
    elif est >= 'M10' and est <= 'M19':
        return 1, 'BRAZO 1', 'Estaciones 10 a 19'
    elif est >= 'M20' and est <= 'M29':
        return 1, 'BRAZO 2', 'Estaciones 20 a 29'
    elif est >= 'M30' and est <= 'M34':
        return 1, 'BRAZO 3', 'Estaciones 30 a 34'
        
    # LINEA 2
    if est in ['M41', 'M42']:
        return 2, 'MUSEO', 'Museo M41/M42'
    elif est >= 'M50' and est <= 'M59':
        return 2, 'BRAZO 1', 'Estaciones 50 a 59'
    elif est >= 'M60' and est <= 'M69':
        return 2, 'BRAZO 2', 'Estaciones 60 a 69'
        
    return None, 'OTROS', 'No Identificado'

# --- MOTOR DE CRUCE REAL ---
def procesar_datos_duros(df_ewm, df_mapa, df_categoria, df_uxc, num_linea_objetivo):
    # 1. Limpieza de estaciones base en el mapa
    df_mapa_limpio = df_mapa[~df_mapa['Estación'].str.contains('_', na=False)].copy()
    
    # Clasificar cada ubicación en su Línea y Brazo correspondiente
    df_mapa_limpio['Linea_Asignada'] = df_mapa_limpio.apply(lambda r: clasificar_linea_y_brazo(r['Estación'], r['Area'])[0], axis=1)
    df_mapa_limpio['Brazo_Asignado'] = df_mapa_limpio.apply(lambda r: clasificar_linea_y_brazo(r['Estación'], r['Area'])[1], axis=1)
    df_mapa_limpio['Layout_Bloque'] = df_mapa_limpio.apply(lambda r: clasificar_linea_y_brazo(r['Estación'], r['Area'])[2], axis=1)
    
    # Filtrar el mapa para quedarse SOLO con la línea bajo estudio
    df_mapa_linea = df_mapa_limpio[df_mapa_limpio['Linea_Asignada'] == num_linea_objetivo].copy()
    
    # 2. Vincular con Categorías
    df_mapa_linea['Posición'] = limpiar_posicion(df_mapa_linea['Posición'])
    df_categoria['Posición'] = limpiar_posicion(df_categoria['Posición'])
    df_map_cat = pd.merge(df_mapa_linea, df_categoria, on='Posición', how='inner')
    
    # Extraer tipos de zona ergonómica
    df_map_cat['CATEGORIA1'] = df_map_cat['CATEGORIA1'].astype(str).str.upper().str.strip()
    df_map_cat['Dificultad'] = df_map_cat['CATEGORIA1'].apply(lambda x: x.split()[0] if ' ' in x else x)
    df_map_cat['Zona_Ergo'] = df_map_cat['CATEGORIA1'].apply(lambda x: 'TRASERA' if 'TRASERA' in x else (x.split()[-1] if ' ' in x else x))
    
    # 3. Cruzar con la demanda del archivo EWM
    df_ewm = df_ewm.rename(columns={'Prod.': 'Cod. SKU', 'Producto': 'Cod. SKU'})
    df_ewm['Cod. SKU'] = limpiar_sku(df_ewm['Cod. SKU'])
    df_map_cat['Cod. SKU'] = limpiar_sku(df_map_cat['Cod. SKU'])
    
    df_maestra = pd.merge(df_ewm, df_map_cat, on='Cod. SKU', how='inner')
    
    # 4. Cruzar con UXC para calcular cajas físicas reales
    df_uxc['Producto'] = limpiar_sku(df_uxc['Producto'])
    df_maestra = pd.merge(df_maestra, df_uxc[['Producto', 'Numerador']], left_on='Cod. SKU', right_on='Producto', how='left')
    df_maestra['Numerador'] = pd.to_numeric(df_maestra['Numerador'], errors='coerce').fillna(9999)
    df_maestra['Ctd.'] = pd.to_numeric(df_maestra['Ctd.'], errors='coerce').fillna(0)
    df_maestra['Cajas_Real'] = np.ceil(df_maestra['Ctd.'] / df_maestra['Numerador'])
    
    return df_maestra

# --- INTERFAZ GRÁFICA ---
st.title("⚖️ Sistema Real de Adherencia PTL por Brazos")
st.markdown("Auditoría automatizada con segmentación estricta de estaciones para Línea 1 y Línea 2.")

# Carga de archivos
st.header("📂 Entrada de Datos")
col1, col2, col3 = st.columns(3)
with col1:
    f_ewm_l1 = st.file_uploader("EWM Línea 1 (Demanda)", type=["csv", "xlsx"])
    f_ewm_l2 = st.file_uploader("EWM Línea 2 (Demanda)", type=["csv", "xlsx"])
with col2:
    f_mapa = st.file_uploader("MAPA Estaciones (Layout)", type=["csv", "xlsx"])
    f_cat = st.file_uploader("CATEGORÍAS (Zonas)", type=["csv", "xlsx"])
with col3:
    f_uxc = st.file_uploader("Maestro UXC (Unidades/Caja)", type=["csv", "xlsx"])

st.divider()

if st.button("📊 ANALIZAR CUMPLIMIENTO DE PARÁMETROS", type="primary", use_container_width=True):
    if f_ewm_l1 and f_ewm_l2 and f_mapa and f_cat and f_uxc:
        
        # Carga masiva de dataframes utilizando la función ya definida arriba
        df_mapa_raw = leer_archivo(f_mapa)
        df_cat_raw = leer_archivo(f_cat)
        df_uxc_raw = leer_archivo(f_uxc)
        df_ewm_l1_raw = leer_archivo(f_ewm_l1)
        df_ewm_l2_raw = leer_archivo(f_ewm_l2)
        
        # Procesamiento real aislado por línea
        df_l1 = procesar_datos_duros(df_ewm_l1_raw, df_mapa_raw, df_cat_raw, df_uxc_raw, 1)
        df_l2 = procesar_datos_duros(df_ewm_l2_raw, df_mapa_raw, df_cat_raw, df_uxc_raw, 2)
        
        tab_l1, tab_l2 = st.tabs(["🔴 REGLAS MAPPED: LÍNEA 1", "🔵 REGLAS MAPPED: LÍNEA 2"])
        
        # ==========================================
        # CONTROL VISUAL: LÍNEA 1
        # ==========================================
        with tab_l1:
            if len(df_l1) > 0:
                tot_docs_l1 = df_l1['Documento'].nunique()
                tot_uds_l1 = df_l1['Ctd.'].sum()
                
                st.subheader("📋 Fichas de Cumplimiento de Parámetros (L1)")
                
                # --- PARÁMETRO: MUSEO M01 ---
                df_mus_l1 = df_l1[df_l1['Brazo_Asignado'] == 'MUSEO']
                docs_mus_l1 = df_mus_l1['Documento'].nunique() if len(df_mus_l1) > 0 else 0
                pct_mus_l1 = (docs_mus_l1 / tot_docs_l1) * 100 if tot_docs_l1 > 0 else 0
                
                # --- PARÁMETRO: BRAZO 1 (M10-M19) ---
                df_b1_l1 = df_l1[df_l1['Brazo_Asignado'] == 'BRAZO 1']
                uds_b1_l1 = df_b1_l1['Ctd.'].sum() if len(df_b1_l1) > 0 else 0
                pct_b1_l1 = (uds_b1_l1 / tot_uds_l1) * 100 if tot_uds_l1 > 0 else 0
                
                c1, c2 = st.columns(2)
                with c1:
                    if pct_mus_l1 < 30.0:
                        st.success(f"🏠 **Volumen Museo (Estación M01):** Encontrado {round(pct_mus_l1, 1)}% de documentos.\n\n🟢 **CUMPLIDO (< 30%)**")
                    else:
                        st.error(f"🏠 **Volumen Museo (Estación M01):** Encontrado {round(pct_mus_l1, 1)}% de documentos.\n\n🔴 **NO CUMPLIDO (Límite < 30%)**")
                with c2:
                    if pct_b1_l1 < 50.0:
                        st.success(f"💪 **Volumen Brazo 1 (Estaciones M10-M19):** {round(pct_b1_l1, 1)}% de las unidades totales.\n\n🟢 **CUMPLIDO (< 50%)**")
                    else:
                        st.error(f"💪 **Volumen Brazo 1 (Estaciones M10-M19):** {round(pct_b1_l1, 1)}% de las unidades totales.\n\n🔴 **NO CUMPLIDO (Límite < 50%)**")
                
                # --- PARÁMETRO TRASERAS L1 ---
                df_tras_l1 = df_l1[df_l1['Zona_Ergo'] == 'TRASERA']
                cajas_max_tras_l1 = df_tras_l1.groupby('Posición')['Cajas_Real'].sum().max() if len(df_tras_l1) > 0 else 0
                st.markdown("---")
                if cajas_max_tras_l1 <= 3:
                    st.success(f"⚠️ **Ocupación Física Traseras:** Máximo de {int(cajas_max_tras_l1)} cajas por ubicación trasera.\n\n🟢 **CUMPLIDO (<= 3 Cajas)**")
                else:
                    st.error(f"⚠️ **Ocupación Física Traseras:** Detectado máximo de {int(cajas_max_tras_l1)} cajas en una posición.\n\n🔴 **EXCEDIDO (Límite <= 3 Cajas)**")
                
                st.markdown("#### Distribución de Unidades por Bloque Técnico - Línea 1")
                df_graf_l1 = df_l1.groupby('Layout_Bloque').agg(Unidades_Totales=('Ctd.', 'sum')).reset_index()
                fig_l1 = px.bar(df_graf_l1, x='Layout_Bloque', y='Unidades_Totales', color='Layout_Bloque', title="Volumen Real Procesado por cada Brazo/Bloque en L1")
                st.plotly_chart(fig_l1, use_container_width=True)
                
            else:
                st.warning("Sin transacciones detectadas para la Línea 1.")

        # ==========================================
        # CONTROL VISUAL: LÍNEA 2
        # ==========================================
        with tab_l2:
            if len(df_l2) > 0:
                tot_docs_l2 = df_l2['Documento'].nunique()
                tot_uds_l2 = df_l2['Ctd.'].sum()
                
                st.subheader("📋 Fichas de Cumplimiento de Parámetros (L2)")
                
                # --- PARÁMETRO: MUSEO M41/M42 L2 ---
                df_mus_l2 = df_l2[df_l2['Brazo_Asignado'] == 'MUSEO']
                docs_mus_l2 = df_mus_l2['Documento'].nunique() if len(df_mus_l2) > 0 else 0
                pct_mus_l2 = (docs_mus_l2 / tot_docs_l2) * 100 if tot_docs_l2 > 0 else 0
                
                # --- PARÁMETRO: BRAZO 1 (M50-M59) L2 ---
                df_b1_l2 = df_l2[df_l2['Brazo_Asignado'] == 'BRAZO 1']
                uds_b1_l2 = df_b1_l2['Ctd.'].sum() if len(df_b1_l2) > 0 else 0
                pct_b1_l2 = (uds_b1_l2 / tot_uds_l2) * 100 if tot_uds_l2 > 0 else 0
                
                c1_l2, c2_l2 = st.columns(2)
                with c1_l2:
                    if pct_mus_l2 < 30.0:
                        st.success(f"🏠 **Volumen Museo (Estaciones M41/M42):** Detectado {round(pct_mus_l2, 1)}% de documentos.\n\n🟢 **CUMPLIDO (< 30%)**")
                    else:
                        st.error(f"🏠 **Volumen Museo (Estaciones M41/M42):** Detectado {round(pct_mus_l2, 1)}% de documentos.\n\n🔴 **NO CUMPLIDO (Límite < 30%)**")
                with c2_l2:
                    if pct_b1_l2 < 40.0:
                        st.success(f"💪 **Volumen Brazo 1 (Estaciones M50-M59):** {round(pct_b1_l2, 1)}% de las unidades de la línea.\n\n🟢 **CUMPLIDO (< 40%)**")
                    else:
                        st.error(f"💪 **Volumen Brazo 1 (Estaciones M50-M59):** {round(pct_b1_l2, 1)}% de las unidades de la línea.\n\n🔴 **NO CUMPLIDO (Límite < 40%)**")
                
                # --- PARÁMETRO ENTRADA CRÍTICA L2 ---
                st.markdown("---")
                df_ent_l2 = df_l2[df_l2['Zona_Ergo'] == 'ENTRADA']
                docs_ent_l2 = df_ent_l2['Documento'].nunique() if len(df_ent_l2) > 0 else 0
                pct_ent_l2 = (docs_ent_l2 / tot_docs_l2) * 100 if tot_docs_l2 > 0 else 0
                
                if 30.0 <= pct_ent_l2 <= 40.0:
                    st.success(f"🚪 **Concentración Zonas Entrada L2:** {round(pct_ent_l2, 1)}% de los documentos (Rango: 30% a 40%).\n\n🟢 **CUMPLIDO**")
                else:
                    st.error(f"🚪 **Concentración Zonas Entrada L2:** {round(pct_ent_l2, 1)}% de los documentos (Fuera de Rango: 30% - 40%).\n\n🔴 **ALERTA DE DESBALANCEO**")
                
                st.markdown("#### Distribución de Unidades por Bloque Técnico - Línea 2")
                df_graf_l2 = df_l2.groupby('Layout_Bloque').agg(Unidades_Totales=('Ctd.', 'sum')).reset_index()
                fig_l2 = px.bar(df_graf_l2, x='Layout_Bloque', y='Unidades_Totales', color='Layout_Bloque', title="Volumen Real Procesado por cada Brazo/Bloque en L2")
                st.plotly_chart(fig_l2, use_container_width=True)
                
            else:
                st.warning("Sin transacciones detectadas para la Línea 2.")
    else:
        st.warning("⚠️ Carga los 5 archivos requeridos para calcular los bloques reales.")