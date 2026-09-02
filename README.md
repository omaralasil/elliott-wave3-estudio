# ¿Tiene la 3ª onda de Elliott poder predictivo?

**Estudio cuantitativo walk-forward de un patrón técnico bursátil sobre acciones US y europeas (2013–2026).**

No es "un algoritmo que gana dinero". Es un ejercicio de **honestidad cuantitativa**: construir un sistema de detección mecánico y luego **intentar tumbarlo con rigor** — auditando el look-ahead, descomponiendo el retorno en alpha vs. beta, y declarando exactamente dónde se rompe.

> **Alcance de publicación.** Este repo comparte la **metodología, la auditoría y los resultados**. El **módulo de detección funcional y el generador de watchlist/PNG en vivo no son públicos** (ver [Qué se publica y qué no](#qué-se-publica-y-qué-no)). La finalidad es demostrar el proceso, no entregar una herramienta lista para copiar.

---

## Resumen ejecutivo

- Sistema en Python que detecta el **inicio de la Onda 3 de Elliott** sobre velas semanales. Es un **radar manual**, no un bot.
- **Cacé y eliminé un sesgo de look-ahead** que inflaba el Profit Factor de **3,87 → 2,74** (−29%). Que el número *baje* al quitarle al sistema la capacidad de ver el futuro es justo lo que lo hace creíble. Después lo **verifiqué leyendo el motor** (revisión a mano + auditoría adversarial independiente).
- **Edge real pero acotado:** claro en **acciones US** (PF ≈3,5–3,8); en **Europa, no concluyente** (mediana ≈+1% por trade, una moneda al aire). Reportado por separado, no escondido en un promedio.
- **La pregunta grande, respondida con honestidad:** al descomponer el retorno por factores (Carhart 4F), es **mayormente beta de mercado US + un sesgo small-cap**; el **alpha genuino NO es estadísticamente significativo** (~5,6%/año, p=0,063). Batió al índice en bruto, pero no está demostrado que lo bata ajustado por riesgo.
- **Validación 100% histórica** (walk-forward, ~13 años) + auditoría de código completa. Operativa en vivo recién iniciada.

**Writeup completo (con todas las tablas y la reflexión):** [`docs/elliott-writeup.md`](docs/elliot-writeup.md)

---

## La pregunta

La teoría de Elliott es famosa por subjetiva. Este proyecto **no intenta "demostrar Elliott"**, sino responder algo contrastable:

> Si defino la señal de forma **mecánica y reproducible**, ¿la ruptura que marca el inicio de una Onda 3 precede a retornos por encima del azar? Y si los precede, ¿es un edge real o solo estar expuesto al mercado?

## El sistema

```
Zigzag adaptativo por ATR (Wilder, 14)
   → Validación Onda 1 (impulso ≥20%, 10–200 semanas)
   → Validación Onda 2 / corrección ABC (retroceso Fibonacci 0,30–0,75)
   → Línea 1-B (resistencia descendente entre el pico 1 y el punto B)
   → Ruptura confirmada (margen ≥1% + volumen ≥1,3× media de la Onda 2)
   → Señal
```
Holding medio ≈47 semanas (swing largo). Stack: Python 3.11, pandas/NumPy, yfinance, matplotlib, pytest.

## Hallazgos clave

### 1. La auditoría de look-ahead (el corazón del proyecto)
La v1 daba PF 3,87 porque el zigzag etiquetaba pivotes mirando **toda la serie** (datos futuros). Reconstruí el motor en **walk-forward**: para cada semana `t`, el pipeline se rehace usando solo `df.iloc[:t+1]`. El PF cayó a **2,74** — y esa caída *es* el resultado. Las 95 señales que solo existían con look-ahead tenían un PF aislado de 4,68 (las "ganadoras fáciles"). Ver el esqueleto seguro del harness en [`analisis/walkforward_harness.py`](analisis/walkforward_harness.py).

### 2. Es un edge US
| Mercado | Profit Factor | N | Mediana / trade |
|---|---:|---:|---:|
| **US** | **3,53** | 315 | **+13,7%** |
| Europa (agregado) | 1,54 | 120 | **+0,9%** (moneda al aire) |

### 3. ¿Alpha o beta? (regresión de factores Carhart 4F)
| | CAGR | Sharpe | maxDD |
|---|---:|---:|---:|
| Estrategia (US) | 19,1% | 0,93 | −44,3% |
| S&P 500 buy & hold | 12,6% | 0,82 | −31,8% |

**beta = 1,12 · SMB +0,36 (significativo) · alpha ≈+5,6%/año pero NO significativo (p=0,063) · R² 0,67.**
→ Batió al índice en bruto, pero **mayormente por beta + sesgo small-cap**; el alpha no queda demostrado. *(La versión honesta es menos vistosa y mucho más valiosa.)*

## Auditoría (qué intenté para tumbarlo)

- **Look-ahead:** walk-forward + cross-check + **revisión de código a mano + auditoría adversarial** → forward-safe.
- **Concentración:** quitar los 5 mejores trades apenas baja el PF (2,74 → 2,51) → edge de base ancha.
- **Robustez:** stationary bootstrap → PF IC 95% [1,81 – 4,92] (US [2,20 – 6,96]).
- **Un filtro "razonable" revertido con datos:** exigir mercado alcista eliminaba más ganadoras que perdedoras (la Onda 3 nace tras un susto, no en la euforia).
- **Un modelo de ML que NO desplegué** por no superar su umbral predefinido.

## Limitaciones (declaradas, no escondidas)

- Mayormente beta + small-cap; **alpha no demostrado**.
- **El PF es un techo optimista:** la construcción del universo usa datos de fin de muestra (liquidez/spikes) → sesgo de selección + supervivencia; y las salidas asumen fills perfectos sin slippage.
- Riesgo real elevado: drawdown ≈−44% y ~2 años bajo el agua (2022–23).
- Regime-dependent: años perdedores reales (2015, 2018, 2019, 2021).
- Validación histórica; sin track record en vivo aún.

## Estructura del repo
```
├── README.md                     ← estás aquí
├── docs/
│   ├── elliott-writeup.md        ← el estudio completo
│   ├── hoja-parametros.md         ← referencia de parámetros
│   └── auditoria-codigo.md        ← auditoría de look-ahead del motor
├── analisis/
│   ├── walkforward_harness.py     ← esqueleto seguro del backtest walk-forward
│   ├── regresion_factores.py      ← alpha vs beta (Carhart 4F)
│   └── equity_marcada_mercado.py  ← curva de equity real + riesgo
├── resultados/
│   ├── trades.csv                 ← trades del backtest (evidencia)
│   ├── segments.csv               ← métricas segmentadas
│   └── charts/                    ← gráficos históricos anotados
```

## Qué se publica y qué no

**Se publica:** metodología, auditoría, resultados, el esqueleto walk-forward (sin la lógica de detección), los scripts de análisis y gráficos históricos.

**No se publica:** el módulo de detección funcional (zigzag/validadores de onda/línea 1-B/screener de ruptura) ni el generador de watchlist/PNG en vivo. El objetivo del repo es demostrar el **rigor del proceso**, no entregar el detector. Si estuvieses interesado en el motor principal, contáctame sin problema.

## Reproducibilidad
Python 3.11 · pandas, NumPy · yfinance · matplotlib · pytest. Los scripts de `analisis/` son ejecutables sobre `resultados/trades.csv` (requieren internet para descargar índices/factores).

---

*Proyecto personal. No es asesoramiento de inversión.*
[README.md](https://github.com/user-attachments/files/31734852/README.md)
