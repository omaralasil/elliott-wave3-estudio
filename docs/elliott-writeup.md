# ¿Tiene la 3ª onda de Elliott poder predictivo? Un estudio walk-forward sobre acciones US y europeas (2013–2026)

> Escrito bajo una regla: nunca mezclar lo verificado con lo que se cree.
> **Nota sobre datos:** el backtest canónico de detección es el cierre de abril 2026 (**435 señales, PF 2,74**). Un re-run de agosto lo reprodujo (**411 señales, PF 2,95**) — la estabilidad entre ejecuciones es en sí una prueba de robustez. La **descomposición por factores, el análisis de riesgo y la auditoría de código** se hicieron sobre el export/repositorio de agosto y se señalan como tales.

---

## Resumen ejecutivo  

- Sistema en Python que detecta el **inicio de la Onda 3 de Elliott** sobre velas semanales. Es un **radar manual**, no un bot: genera un watchlist, la persona decide.
- **Edge real pero acotado:** claro en **acciones US** (PF 3,5–3,8 · mediana ≈+14% por trade) en walk-forward sin look-ahead; en **Europa, no concluyente** (mediana ≈+1%, moneda al aire), reportado por separado.
- **La pieza central no es "gana dinero".** Es: *construí un sistema y luego lo audité adversarialmente hasta el final — esto sobrevivió, y aquí es exactamente donde se rompe.*
- **Cacé y eliminé un sesgo de look-ahead** que inflaba el Profit Factor de **3,87 a un honesto 2,74** (−29%). El número bajó; por eso me lo creo. Y el motor **pasó después una auditoría de código triple** (revisión a mano + sub-agente adversarial + config): sin look-ahead estructural.
- **La pregunta grande, respondida con honestidad:** al descomponer el retorno por factores, es **mayormente beta de mercado US + un sesgo small-cap**; el **alpha genuino no es estadísticamente significativo** (~5,6%/año, p=0,063). Batió al índice en bruto, pero **no está demostrado que lo bata ajustado por riesgo** — y con mayor drawdown.
- **Estado:** validación histórica + auditoría de código completas. Operativa en vivo recién iniciada.

---

## 1. La pregunta

La teoría de Elliott es famosa y famosamente criticada por subjetiva: dos analistas dibujan ondas distintas sobre el mismo gráfico. Por eso este proyecto **no intenta "demostrar Elliott"**. Intenta responder algo contrastable:

> Si defino la señal de forma **mecánica y reproducible**, ¿la ruptura que marca el inicio de una Onda 3 precede a retornos por encima del azar? Y si los precede, ¿es un edge real o solo estar expuesto al mercado?

Un sistema, reglas fijas, y una evaluación honesta de si funciona. El resto del documento es esa evaluación — incluidas las partes donde no funciona.

## 2. El sistema (cómo detecta)

Pipeline sobre velas semanales (15 años de datos, yfinance):

```
Zigzag adaptativo por ATR (Wilder, 14)
   → Validación Onda 1 (impulso ≥20%, 10–200 semanas)
   → Validación Onda 2 / corrección ABC (retroceso Fibonacci 0,30–0,75)
   → Línea 1-B (resistencia descendente entre el pico 1 y el punto B)
   → Ruptura confirmada (margen ≥1% + volumen ≥1,3× media de la Onda 2)
   → Señal de entrada
```

- **Filosofía: radar, no bot.** El operador descarta señales técnicamente válidas pero con mala narrativa (IPOs recientes, rebotes post-crash extremo) y modula tamaño según contexto macro.
- **Sistema lento:** holding medio ≈47 semanas. No es alta frecuencia.
- **Universo:** ~957 tickers candidatos (mayoría US + varias bolsas europeas); 3 bolsas blacklisteadas empíricamente (PF <1,5). *No es un universo point-in-time — ver Limitaciones.*
- **Stack:** Python 3.11, pandas/NumPy, yfinance (caché Parquet), matplotlib; 42+ tests en pytest.

## 3. ⭐ La auditoría de look-ahead

La primera versión daba un Profit Factor de 3,87. Demasiado bueno — y lo era.

El detector usaba un zigzag "por lotes" que etiquetaba los pivotes mirando **toda la serie**, incluidos datos futuros respecto al momento de la decisión. Es el error más común y más letal de un backtest: el sistema "sabía" cómo terminaba la historia.

Reconstruí el motor en modo **walk-forward**: para cada semana `t` de cada ticker, el pipeline se rehace usando **solo** `df.iloc[:t+1]`. Ningún acceso al futuro. ~186.000 iteraciones (ticker × vela).

**El Profit Factor cayó a 2,74.** Y esa caída *es* el resultado:

- Las **95 señales** que solo existían en el modo con look-ahead tenían un PF aislado de **4,68** — las "ganadoras fáciles" que solo aparecían porque el algoritmo veía el futuro.
- Las señales comunes a ambos modos tenían PF prácticamente idéntico (consistencia real del tracking).

**Verificación posterior a nivel de código (agosto 2026).** No me quedé en "reconstruí el motor": leí y audité el código del motor, y lo sometí a un **sub-agente adversarial independiente** cuya tarea era *romperlo*. Ambas revisiones, más la config de producción, confirman que el núcleo temporal es forward-safe:

- El troceo `df.iloc[:t+1]` es real y alimenta **todo** el pipeline (blindaje arquitectónico).
- Entrada al **cierre de la vela de ruptura**, seguimiento desde `t+1` (no se re-evalúa la vela de entrada).
- Salidas **conservadoras**: el stop se comprueba antes que el objetivo; si ambos caen en la misma vela, gana el stop.
- ATR **causal** (Wilder con cierre desplazado, sin relleno hacia atrás), por lo que precomputar y trocear no filtra futuro.
- Filtro de régimen **causal** (solo mira el índice hasta la fecha de la señal). `walkforward_enabled: true` en producción.

Un sistema que **empeora** cuando le quitas la capacidad de ver el futuro, y que además resiste la lectura línea a línea de su motor, es un sistema en cuyo número puedo confiar.

> **Honestidad, también con mis propios errores:** durante la auditoría diagnostiqué que la concentración de cierres en la franja 39–52 semanas era look-ahead residual. Estaba equivocado: se debe al cierre forzado por tiempo (`max_holding_weeks=52`). Corregí el diagnóstico. La auditoría también se audita.

## 4. Resultados

### 4.1 El titular real: es un edge US

El PF agregado esconde una verdad que prefiero enseñar que ocultar: **el edge está en US.**

| Mercado | Profit Factor | N | Retorno medio | **Mediana** |
|---|---:|---:|---:|---:|
| **US** | **3,53** | 315 | +17,0% | **+13,7%** |
| Europa (agregado) | 1,54 | 120 | +6,1% | **+0,9%** |

En US, la señal muestra un edge claro. En Europa, la **mediana del trade es +0,9% — literalmente una moneda al aire**: su media ligeramente positiva la sostienen unos pocos ganadores. Reportarlo por separado es más honesto que un promedio que disimula la parte débil.

### 4.2 Escenario de gestión de salida. El "por qué", no solo el "qué")

Sobre las **mismas 435 señales**, tres formas de gestionar la salida:

| Escenario | Salida | PF | Retorno medio | **Mediana** | Win Rate | Holding |
|---|---|---:|---:|---:|---:|---:|
| **A** | Stop conservador en P0 | **2,74** | +14,0% | **+10,2%** | 63,2% | 46,9 sem |
| B | Stop agresivo en C | 2,42 | +10,9% | +0,7% | 50,6% | 36,2 sem |
| C | Trailing dinámico | 2,18 | +7,5% | 0,0% | 46,7% | 32,8 sem |

Al descomponer los retornos, **la lógica de salida de B y C destruye valor por sí sola** — todo su resultado positivo viene del residuo de cierres por tiempo, no de sus stops. A es superior porque su gestión está *alineada* con cómo se comporta el sistema. **La mediana lo confirma:** en A el trade típico gana +10,2%; en B y C es ~0 (viven de la cola).

> **Nota sobre "expectativa":** la expectativa real por operación es el **retorno medio, +14,0%** (Esc. A). El código imprime además un campo "Expectancy" con una fórmula más estrecha (excluye el ~74% que cierra por tiempo); no es la expectativa del sistema y no la uso como cifra pública.

### 4.3 Por año: sobrevive a 2022, pero el edge es grumoso

Años perdedores reales: **2015, 2018, 2019** (y en el re-run de agosto, también **2021**, con PF 0,23). 2022 (bajista, SPX ≈−19%) se mantuvo rentable (PF 2,45) y está **dentro** del walk-forward. El resultado lo cargan unos pocos años muy fuertes (2016, 2020, 2023–25). **No es un goteo estable: es regime-dependent, con drawdowns reales.**

> **Un detalle no obvio y revelador:** 2019 y 2021 —dos de los peores años del sistema— fueron años **muy alcistas** del S&P (+29%, +27%). El sistema perdió *en mercados que subían fuerte*. Eso dice que **no es beta simple** (no sigue mecánicamente al mercado), pero tampoco alpha limpio (se perdió subidas enormes). Es momentum episódico. Justo esto motivó la pregunta de la §4.5.

### 4.4 ¿Vive el edge de unos pocos trades con suerte? No

| Test de concentración (Escenario A) | Resultado |
|---|---|
| Mediana del retorno por trade | **+10,2%** (el trade típico gana sólido) |
| Peso de los 5 mejores trades en el P&L neto | 13,4% |
| **PF quitando los 5 mejores trades** | **2,51** (desde 2,74 — apenas cambia) |

El edge es **de base ancha**, no un artefacto de un puñado de aciertos enormes.
**Caveat honesto en la otra dirección:** sí hay concentración **por nombre** — los 10 tickers principales acumulan ~48% del P&L. Y el tramo reciente (2023-25) se apoya en semiconductores/industriales US. Algo a declarar.

### 4.5 ⭐ La pregunta grande: ¿alpha o beta?

Un backtest bonito no significa nada si el retorno es, simplemente, estar expuesto al mercado en el mayor bull de la historia. Así que reconstruí la **curva de equity marcada a mercado real** (revalorizando las posiciones abiertas semana a semana) y la sometí a una **regresión de factores Carhart de 4 factores** (mercado, tamaño, valor, momentum), con errores estándar Newey-West.

**Riesgo/retorno real (sub-libro US):**

| | CAGR | Sharpe | maxDD | Underwater más largo |
|---|---:|---:|---:|---|
| **Estrategia US** | 19,1% | 0,93 | **−44,3%** | ~2 años (2022–2023) |
| S&P 500 buy & hold | 12,6% | 0,82 | −31,8% | — |

**Descomposición por factores (mensual, N=154):**

- **beta de mercado = 1,12** → exposición plena, ligeramente apalancada.
- **SMB = +0,36 (significativo, p=0,001)** → un **sesgo small-cap** real: parte del "edge" es cobrar la prima de tamaño, no destreza.
- **alpha ≈ +5,6% anual, pero NO significativo (p=0,063).** Un indicio, no una prueba.
- **R² = 0,67:** dos tercios del retorno los explican mercado + factores.

**Veredicto honesto:** el sistema batió al S&P en retorno bruto (19,1% vs 12,6%), **pero mayormente por beta>1 + sesgo small-cap**. Ajustado por riesgo la ventaja es modesta (Sharpe 0,93 vs 0,82) y **con peor drawdown (−44% vs −32%)** y ~2 años bajo el agua. **El alpha genuino no queda demostrado.**

> *Caveat metodológico:* la reconstrucción rebalancea equal-weight semanalmente sin costes, lo que probablemente **infla** el CAGR y el alpha. Lo robusto no es el nivel exacto, sino la conclusión: **mayormente beta + tamaño, alpha no probado.**

Este es, para mí, el resultado más valioso del proyecto. No porque sea espectacular —no lo es—, sino porque es **la verdad**: es fácil escribir "mi sistema da 19% anual y bate al mercado"; es mucho más difícil, y mucho más útil, llegar hasta aquí y decir *"cuando lo descompongo, es sobre todo beta y prima de tamaño, y no puedo demostrar alpha"*.

## 5. Dos cosas que aprendí diciendo "no"

**Un filtro que "sonaba bien" resultó contraproducente.** Exigir que el índice llevara 6 meses alcista antes de operar parecía sensato. Los datos dijeron lo contrario: eliminaba 127 señales ganadoras (+31,7% de media) y solo 59 perdedoras. **La Onda 3 nace tras un susto, no en un mercado eufórico.** Filtro revertido. Conecta con el hallazgo intelectual más interesante: la relación entre el drawdown del SPX y la rentabilidad **no es lineal, es una U invertida** — la mejor zona es *tras una corrección* (PF 3,3–3,9), la peor *con el mercado en máximos* (PF 1,5–1,8). Se usa como etiqueta informativa, no como filtro.

**Un modelo de ML que no desplegué.** Intenté sustituir el score heurístico por una regresión logística. No superó el umbral predefinido (Spearman OOS 0,058 vs 0,15 exigido). Un sanity check con datos sintéticos confirmó que el fallo era real —ausencia de señal en las features—, no un bug. **No se desplegó**, exactamente como marcaba el protocolo.

## 6. Auditoría adversarial: qué intenté para tumbarlo

| Amenaza | Test | Veredicto |
|---|---|---|
| Look-ahead bias | Walk-forward + cross-check 95 señales + **auditoría de código triple** | ✅ Resuelto (3,87→2,74), verificado en código |
| Concentración por mercado | PF desagregado por bolsa | ✅ Declarado: el edge es US |
| Filtro "razonable" pero dañino | Validación empírica del momentum | ✅ Revertido con datos |
| Señal macro espuria | Test de placebo (1000 shuffles) + holdout | ✅ Solo 1 de 3 features sobrevive |
| Concentración de P&L (top-5 trades) | PF excluyendo los 5 mejores | ✅ Robusto: 2,74 → 2,51 |
| Independencia estadística | Stationary bootstrap → IC del PF | ✅ PF IC 95% [1,81 – 4,92] (US [2,20 – 6,96]): edge no es azar |
| **¿Bate al mercado? (alpha vs beta)** | Equity marcada a mercado + Carhart 4F | ⚠️ **Mayormente beta + small-cap; alpha NO significativo** (§4.5) |
| Censura temporal | END_DATA aislado vs resueltos | ✅ No infla: los inmaduros arrastran abajo |
| **Selección de universo** | Lectura del código de filtros de calidad | ⚠️ **Sesgo confirmado**: liquidez/spikes usan datos de fin de muestra → infla (ver §7) |
| Gap de ejecución (fills) | Salidas asumen fill perfecto en velas semanales | ⚠️ Optimista; infla el PF (re-run entrada/salida lunes: pendiente) |
| Sesgo de supervivencia | Universo de tickers activos | ⚠️ Confirmado en código, magnitud no cuantificada |

## 7. Limitaciones (declaradas, no escondidas)

- **Mayormente beta + small-cap; alpha no demostrado (§4.5).** El sistema captura sobre todo exposición al mercado US y a la prima de tamaño.
- **El PF reportado es un techo optimista.** Dos sesgos residuales, confirmados leyendo el código, lo inflan:
  - **Selección de universo con datos de fin de muestra:** la inclusión de un ticker se decide con su liquidez de las últimas 52 semanas y sus spikes en toda la serie, y luego se backtestea desde 2013 → look-ahead de selección + supervivencia (universo de tickers *activos*, sin deslistados). *Fix identificado: recalcular esos filtros de forma causal dentro del walk-forward.*
  - **Fills perfectos:** las salidas asumen ejecución exacta al stop/target sin slippage ni gaps; en velas semanales el rango intra-vela es enorme.
- **El backtest no es idéntico a la herramienta en vivo:** en producción se fusionan dos perfiles de detección y se toma un ganador por ticker; el backtest evalúa un solo perfil y todos los pares. Parte de lo que ve el usuario no se ha backtesteado con exactitud.
- **Riesgo real elevado:** drawdown de cartera ≈ −44% y ~2 años bajo el agua (2022–23). Operarlo exige tolerar más riesgo que el índice.
- **Independencia:** ~435 trades con clustering temporal y 72% US → el IC real es más ancho de lo que N sugiere.
- **Validación 100% histórica** hasta ahora; la operativa en vivo acaba de empezar.
- **El score heurístico interno NO es predictivo** (Spearman ≈ 0 sobre los trades). Cualquier "cluster de score alto" es concentración estadística, no una regla; el watchlist se ordena por distancia al breakout.

## 8. Qué me llevo

- Cómo un sesgo sutil de anticipación puede inflar un backtest un 29%, cómo cazarlo, y cómo **verificarlo leyendo el motor** (no solo confiando en el diseño).
- Que **"bate al mercado en bruto" y "genera alpha" son cosas distintas**, y que separarlas —con una regresión de factores— es lo que distingue a un analista de alguien que se cree sus propios números.
- Que la honestidad estadística —declarar la potencia limitada, revertir lo que no funciona, no desplegar un modelo bajo su umbral, decir "es mayormente beta"— **es parte del resultado**, no una nota al pie.

## 8.bis Validación en vivo (en curso) `[rellenar con tus datos]`

Sigo las detecciones del sistema **en tiempo real** desde `10-05-2026`, registrando cada señal que dispara el código en un diario. Es forward-testing puro. **Aviso honesto:** con un holding medio de ~47 semanas, casi ningún trade ha tenido tiempo de cerrarse — muestra pequeña e inmadura, **demasiado pronto para concluir nada**. Todas ellas las registro en un archivo de Excel mediante una API implementada al código principal.

### Apéndice — parámetros clave
`min_wave1_pct 0,20 · fib 0,30–0,75 · volumen ruptura 1,3× · margen ruptura 1% · max_holding 52 sem · dedup 12 sem · blacklist [DE, HE, CO]`
