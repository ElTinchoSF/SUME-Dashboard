# Guía de Tema Visual FBCB-UNL para Streamlit

## Paleta de Colores

| Variable | Color | Hex | Uso |
|----------|-------|-----|-----|
| Primario | Verde FBCB | `#00A94F` | Botones, acentos, bordes |
| Hover | Verde oscuro | `#008C41` | Hover de botones |
| Claro | Verde claro | `#b2e8c4` | Bordes suaves |
| bg-50 | Verde muy claro | `#f0fdf4` | Fondos de sidebar, tabs |
| bg-100 | Verde claro | `#dcfce7` | Fondos de cards, labels |
| UNL Turquesa | Turquesa UNL | `#0088AA` | Acentos UNL |
| Oscuro | Verde oscuro | `#244C5A` | Texto headings, footer |
| Gris | Gris | `#575756` | Texto secundario |

## Tipografía

| Elemento | Fuente | Pesos |
|----------|--------|-------|
| Headings (h1-h3) | Montserrat | 600, 700 |
| Botones | Montserrat | 600 |
| Tabs | Montserrat | 500 |
| Labels | Montserrat | 600 |
| Body text | Lato | 400, 700 |
| Subtítulos | Lato | 400 |

---

## Estructura de Archivos

```
config/
├── streamlit_theme.css    # Estilos CSS del tema
├── streamlit_theme.py     # Helper de Python
└── normalization_rules.yaml
```

---

## Uso Rápido

### 1. Copiar los archivos

Copiar `config/streamlit_theme.css` y `config/streamlit_theme.py` a tu proyecto.

### 2. Configurar app.py

```python
import streamlit as st
from config.streamlit_theme import apply_theme, create_header, create_footer

# PRIMERO: Configurar la página (debe ser lo primero)
st.set_page_config(
    page_title="Mi Dashboard",
    page_icon="📊",
    layout="wide",                    # OBLIGATORIO para layout completo
    initial_sidebar_state="expanded"
)

# SEGUNDO: Aplicar el tema
apply_theme("config/streamlit_theme.css")

# TERCERO: Header institucional
create_header(
    title="Mi Dashboard",
    subtitle="Descripción del dashboard",
    logo_path="logo.png",             # Opcional
    org_info="FBCB • UNL"             # Info a la derecha
)

# CONTENIDO...
```

### 3. Sidebar

```python
with st.sidebar:
    st.markdown('<p class="sidebar-nav-title">📊 Navegación</p>', unsafe_allow_html=True)
    
    # Filtros
    fecha = st.date_input("Fecha")
    
    # Navegación
    page = st.radio(
        "Página",
        ["📈 Vista General", "📋 Detalles"],
        label_visibility="collapsed"
    )
```

### 4. Footer

```python
# Al final de app.py
create_footer(
    app_name="Mi App v1.0",
    org_name="Facultad de Bioquímica y Ciencias Biológicas",
    extra_info="Universidad Nacional del Litoral"
)
```

---

## Funciones del Helper

### `apply_theme(css_path)`

Carga y aplica el CSS del tema.

```python
apply_theme("config/streamlit_theme.css")
```

### `create_header(title, subtitle, logo_path, org_info)`

Crea el header institucional verde con esquinas redondeadas.

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `title` | str | Título principal |
| `subtitle` | str | Subtítulo descriptivo |
| `logo_path` | str | Ruta al logo (opcional) |
| `org_info` | str | Info a la derecha (default: "FBCB • UNL") |

```python
create_header(
    title="Dashboard de Análisis",
    subtitle="Sistema de Gestión de Datos",
    logo_path="Docs/logo.png",
    org_info="FBCB • UNL"
)
```

### `create_footer(app_name, org_name, extra_info)`

Crea el footer institucional oscuro con bordes redondeados.

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `app_name` | str | Nombre de la app |
| `org_name` | str | Nombre de la organización |
| `extra_info` | str | Info adicional (opcional) |

```python
create_footer(
    app_name="Mi Dashboard v2.0",
    org_name="Facultad de Bioquímica y Ciencias Biológicas",
    extra_info="Universidad Nacional del Litoral"
)
```

### `COLORS`

Diccionario con la paleta de colores para usar en gráficos Plotly.

```python
from config.streamlit_theme import COLORS

# Usar en Plotly
import plotly.express as px

fig = px.bar(
    df, 
    x="category", 
    y="value",
    color_discrete_sequence=[COLORS['primary']]
)
```

| Key | Color | Hex |
|-----|-------|-----|
| `primary` | Verde FBCB | `#00A94F` |
| `primary_dark` | Verde hover | `#008C41` |
| `primary_light` | Verde claro | `#b2e8c4` |
| `bg_50` | Fondo claro | `#f0fdf4` |
| `bg_100` | Fondo verde | `#dcfce7` |
| `unl_turquoise` | Turquesa UNL | `#0088AA` |
| `unl_dark` | Verde oscuro | `#244C5A` |
| `gray` | Gris | `#575756` |

### `CHART_FONTS`

Configuración de fuentes para gráficos Plotly.

```python
from config.streamlit_theme import CHART_FONTS

fig.update_layout(font=CHART_FONTS)
```

---

## CSS Personalizado

### Agregar estilos adicionales

```python
st.html("""
    <style>
    /* Mis estilos personalizados */
    .mi-clase {
        background-color: #00A94F;
        color: white;
        padding: 1rem;
        border-radius: 8px;
    }
    </style>
""")
```

### Selectores útiles de Streamlit

```css
/* Sidebar */
[data-testid="stSidebar"] { }

/* Contenedor principal */
.stMainBlockContainer { }

/* Métricas */
.stMetric { }

/* Botones */
.stButton > button { }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { }

/* DataFrame */
.stDataFrame { }

/* Gráficos Plotly */
.stPlotlyChart { }
```

---

## Ejemplo Completo

```python
"""
Dashboard de Ejemplo - Tema FBCB-UNL
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from config.streamlit_theme import (
    apply_theme, create_header, create_footer, 
    COLORS, CHART_FONTS
)

# ══════════════════════════════════════════════
# 1. CONFIGURACIÓN INICIAL
# ══════════════════════════════════════════════
st.set_page_config(
    page_title="Dashboard Ejemplo",
    page_icon="📊",
    layout="wide"
)

# ══════════════════════════════════════════════
# 2. APLICAR TEMA
# ══════════════════════════════════════════════
apply_theme("config/streamlit_theme.css")

# ══════════════════════════════════════════════
# 3. HEADER
# ══════════════════════════════════════════════
create_header(
    title="Dashboard Ejemplo",
    subtitle="Análisis de Datos Administrativos",
    logo_path="logo.png"
)

# ══════════════════════════════════════════════
# 4. SIDEBAR
# ══════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        '<p class="sidebar-nav-title">📊 Navegación</p>', 
        unsafe_allow_html=True
    )
    
    # Filtros
    fecha_inicio = st.date_input("Fecha inicio")
    fecha_fin = st.date_input("Fecha fin")
    
    # Navegación
    page = st.radio(
        "Página",
        ["📈 Resumen", "📋 Detalles", "📊 Gráficos"],
        label_visibility="collapsed"
    )

# ══════════════════════════════════════════════
# 5. CONTENIDO
# ══════════════════════════════════════════════
if page == "📈 Resumen":
    st.markdown("## Resumen")
    
    # KPIs
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Expedientes", 150)
    with col2:
        st.metric("Movimientos", 1234)
    with col3:
        st.metric("Días Promedio", 5.2)
    
    # Gráfico
    df = pd.DataFrame({
        'Categoría': ['A', 'B', 'C', 'D'],
        'Valor': [23, 45, 56, 78]
    })
    
    fig = px.bar(
        df, 
        x='Categoría', 
        y='Valor',
        color_discrete_sequence=[COLORS['primary']]
    )
    fig.update_layout(font=CHART_FONTS)
    st.plotly_chart(fig, use_container_width=True)

elif page == "📋 Detalles":
    st.markdown("## Detalles")
    st.dataframe(df)

elif page == "📊 Gráficos":
    st.markdown("## Gráficos")
    # Más gráficos...

# ══════════════════════════════════════════════
# 6. FOOTER
# ══════════════════════════════════════════════
create_footer(
    app_name="Dashboard Ejemplo v1.0",
    org_name="Facultad de Bioquímica y Ciencias Biológicas"
)
```

---

## Notas Importantes

1. **`st.set_page_config()`** debe ser lo PRIMERO en ejecutarse
2. **`apply_theme()`** debe ir después de `set_page_config()` y antes de cualquier contenido
3. **`layout="wide"`** es OBLIGATORIO para que el layout funcione correctamente
4. Usar **`st.html()`** en vez de `st.markdown()` para CSS (evita margen extra arriba)
5. El header y footer se agregan como HTML inline

---

## Solución de Problemas

### El header no se ve bien
- Verificar que `layout="wide"` esté en `set_page_config()`
- Asegurarse de que el logo existe en la ruta especificada

### Los botones no tienen color
- Verificar que `apply_theme()` se ejecutó antes del contenido

### El sidebar tiene mucho espacio
- El tema ya reduce el espacio automáticamente
- Si persiste, agregar `[data-testid="stSidebarHeader"] { height: 2rem; }`

### Aparece "Deploy" de Streamlit
- El tema ya oculta el botón automáticamente
- Si aparece, verificar que el CSS se cargó correctamente
